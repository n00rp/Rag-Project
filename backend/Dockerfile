FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY src/DocAssistant.Api/DocAssistant.Api.csproj src/DocAssistant.Api/
RUN dotnet restore src/DocAssistant.Api/DocAssistant.Api.csproj
COPY src/DocAssistant.Api src/DocAssistant.Api
RUN dotnet publish src/DocAssistant.Api/DocAssistant.Api.csproj -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app .
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "DocAssistant.Api.dll"]
