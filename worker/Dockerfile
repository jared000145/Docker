FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY Worker.csproj .
RUN dotnet restore Worker.csproj
COPY . .
RUN dotnet publish Worker.csproj -c Release -o /app/publish --no-restore
FROM mcr.microsoft.com/dotnet/runtime:10.0
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgssapi-krb5-2 && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 10001 appuser
COPY --from=build --chown=appuser:appuser /app/publish .
USER appuser
ENV HEARTBEAT_FILE=/tmp/worker-heartbeat
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 CMD test -f "$HEARTBEAT_FILE" && find "$HEARTBEAT_FILE" -mmin -1 | grep -q .
ENTRYPOINT ["dotnet", "Worker.dll"]
