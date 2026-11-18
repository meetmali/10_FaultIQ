# FaultIQ API image: ASP.NET Core on .NET 10 LTS (ADR 0007).
# Multi-arch (amd64 and arm64). The build runs natively on the build machine and produces a portable,
# framework-dependent app with no native dependencies, so one build output serves every architecture.

FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:10.0.403-noble AS build
WORKDIR /src

# Restore first (cached layer). Locked mode fails if packages.lock.json is out of date.
COPY global.json Directory.Build.props Directory.Packages.props ./
COPY src/FaultIQ.Api/FaultIQ.Api.csproj src/FaultIQ.Api/packages.lock.json src/FaultIQ.Api/
RUN dotnet restore src/FaultIQ.Api/FaultIQ.Api.csproj --locked-mode

COPY src/ src/
RUN dotnet publish src/FaultIQ.Api/FaultIQ.Api.csproj -c Release -o /out --no-restore -p:UseAppHost=false \
    && mkdir -p /staging/data/uploads

# Chiseled runtime: no shell or package manager, runs as non-root 'app' (UID 1654).
FROM mcr.microsoft.com/dotnet/aspnet:10.0.14-noble-chiseled
WORKDIR /app
COPY --from=build /out .
COPY --from=build --chown=1654:1654 /staging/data /app/data

ENV ASPNETCORE_HTTP_PORTS=8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "FaultIQ.Api.dll"]
