param(
  [int]$Port = 7860
)

$ErrorActionPreference = "Stop"
$env:DIALECT_SERVICE_PORT = "$Port"
python -m uvicorn app.main:app --host 0.0.0.0 --port $Port --reload

