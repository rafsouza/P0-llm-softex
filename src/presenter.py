import csv
import json
from datetime import datetime
from pathlib import Path
from fastapi.responses import FileResponse, JSONResponse

from src.response_parser import EXPECTED_FIELDS


class ResultPresenter:
    ALLOWED_EXTENSIONS = {".csv", ".json"}

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def ensure_output_dir(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_event(self, event_data: dict, output_format: str) -> Path:
        """CSV ou JSON com timestamp para evitar sobrescrita."""
        self.ensure_output_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filepath = self.output_dir / f"evento_{timestamp}.{output_format}"

        if output_format == "csv":
            with open(filepath, mode="w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=list(EXPECTED_FIELDS),
                    extrasaction="ignore",
                )
                writer.writeheader()
                writer.writerow(event_data)
        else:
            with open(filepath, mode="w", encoding="utf-8") as json_file:
                json.dump(event_data, json_file, ensure_ascii=False, indent=4)

        return filepath

    def build_data_response(self, event_data: dict, filepath: Path) -> JSONResponse:
        """Retorno dos dados extraídos."""
        return JSONResponse(
            content=event_data,
            headers={
                "X-File-Saved": filepath.name,
                "Access-Control-Expose-Headers": "X-File-Saved",
            },
        )

    def build_download_response(self, filepath: Path, output_format: str) -> FileResponse:
        """Download do arquivo gerado."""
        media_type = (
            "text/csv; charset=utf-8"
            if output_format == "csv"
            else "application/json; charset=utf-8"
        )
        return FileResponse(
            path=filepath,
            filename=filepath.name,
            media_type=media_type,
            headers={
                "X-File-Saved": filepath.name,
                "Access-Control-Expose-Headers": "Content-Disposition, X-File-Saved",
            },
        )

    def list_files(self) -> dict:
        """Listagem de todos os arquivos CSV e JSON na pasta de saída."""
        base_dir = self.output_dir.resolve()
        if not base_dir.exists():
            return {"output_dir": str(self.output_dir), "total": 0, "files": []}

        files = sorted(
            [
                f.name
                for f in base_dir.iterdir()
                if f.is_file() and f.suffix.lower() in self.ALLOWED_EXTENSIONS
            ],
            reverse=True,
        )
        return {
            "output_dir": str(self.output_dir),
            "total": len(files),
            "files": files,
        }

    def resolve_safe_file(self, filename: str) -> Path | None:
        """Validação do nome do arquivo."""
        base_dir = self.output_dir.resolve()
        target_file = (base_dir / filename).resolve()

        if (
            target_file.parent != base_dir
            or target_file.suffix.lower() not in self.ALLOWED_EXTENSIONS
        ):
            return None

        return target_file
   