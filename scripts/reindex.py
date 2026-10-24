"""Index every document again, through the API: download the original, delete the document, upload it under the same name.

Needed after the embedding model or its dimension changed (RESET_VECTORS_ON_DIM_CHANGE emptied the vectors). Document ids
change, so older chat answers no longer link to their source documents.

    python scripts/reindex.py [--api http://localhost:8080/api]
"""
import argparse
import json
import time
import urllib.request
import uuid


def call(req):
    return urllib.request.urlopen(req, timeout=300).read()


def upload(api: str, name: str, data: bytes) -> None:
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: application/pdf\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    call(urllib.request.Request(api + "/documents", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8080/api")
    a = ap.parse_args()
    docs = json.loads(call(urllib.request.Request(a.api + "/documents")))
    files = [(d["id"], d["fileName"], call(urllib.request.Request(f"{a.api}/documents/{d['id']}/file"))) for d in docs]
    for doc_id, name, data in files:  # all downloaded first: nothing is deleted unless every original was readable
        call(urllib.request.Request(f"{a.api}/documents/{doc_id}", method="DELETE"))
        upload(a.api, name, data)
        print("uppladdad", name, flush=True)
    while True:
        status = [d["status"] for d in json.loads(call(urllib.request.Request(a.api + "/documents")))]
        print(f"{status.count('Ready')}/{len(status)} klara, {status.count('Failed')} misslyckade", flush=True)
        if all(s in ("Ready", "Failed") for s in status):
            break
        time.sleep(10)


if __name__ == "__main__":
    main()
