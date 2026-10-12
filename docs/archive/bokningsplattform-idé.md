# Projektuppdrag: Mikrotjänstbaserad Bokningsplattform med Clean Architecture

## Mål & Syfte
Bygga ett skalbart backend-system för resurshantering och bokning (t.ex. mötesrum, utrustning eller tjänster). Projektet ska demonstrera djup förståelse för C#/.NET 8, Clean Architecture, testdriven utveckling (TDD), mikrotjänster och CI/CD.

## Systemarkitektur & Teknikstack
1. **Arkitekturmönster:** Clean Architecture / CQRS (MediatR), Domain-Driven Design (DDD)-principer.
2. **Backend (.NET 8 Web API):**
   - **Identity Service:** Hanterar användare, roller och JWT-tokens.
   - **Resource Service:** CRUD för resurser/produkter med tillgänglighetskalender.
   - **Booking Service:** Hanterar bokningar, validering av krockande tider och statusuppdateringar.
3. **Databas & Persistens:**
   - PostgreSQL eller SQL Server med Entity Framework Core (Code-First Migrations).
   - Redis för caching av tillgängliga tider/resurser.
4. **Tester & Verktyg:**
   - xUnit, FluentAssertions, Moq/NSubstitute för enhetstester och integrationstester.
   - Docker för containerisering.
   - GitHub Actions för automatiska byggen och tester.

## Kravspecifikation per Milstolpe

### Milstolpe 1: Domänmodellering & Clean Architecture
- Sätt upp lösningen i .NET med följande projektstruktur per tjänst:
  - `Domain` (Entities, Value Objects, Enums, Exceptions)
  - `Application` (Interfaces, CQRS Handlers via MediatR, DTOs, Validators med FluentValidation)
  - `Infrastructure` (DbContext, Repositories, External Services)
  - `Api` (Controllers/Minimal APIs, Middleware, Swagger)

### Milstolpe 2: Affärslogik & Validering
- Implementera bokningslogik som förhindrar dubbelbokningar (samtidiga anrop/concurrency controls).
- Implementera global felhantering via custom middleware (ProblemDetails RFC 7807).
- Lägg till JWT-baserad autentisering och rollbaserad auktorisering (t.ex. Admin vs Användare).

### Milstolpe 3: Caching & Asynkron Kommunikation
- Lägg till Redis cache för att snabba upp läsningar av lediga resurser.
- Sätt upp grundläggande event-hantering (t.ex. när en bokning skapas skickas en bekräftelse/logg).

### Milstolpe 4: Testning & Dokumentation (Portfolio-fokus)
- Skriv omfattande enhetstester för affärslogik och CQRS-handlers (satsa på >80% code coverage).
- Skriv integrationstester för API-endpoints med `WebApplicationFactory`.
- Skriv en professionell `README.md` med arkitekturdiagram (Mermaid.js), Swagger-dokumentation och Docker-instruktioner.

## Claude Instruktion
Hjälp mig att steg för steg bygga detta projekt. Börja med att ge mig den exakta .NET-lösningens struktur (solution structure), inklusive alla `.csproj`-filer och mappar enligt Clean Architecture, samt domänmodellen för `Booking` och `Resource`.