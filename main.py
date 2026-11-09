import os
import tempfile
import subprocess

from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

app = FastAPI(
    title="MJR Downloader API",
    description="Authorized media processing service",
    version="1.0.0"
)

MAX_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_TYPES = {
    "video/mp4",
    "video/quicktime",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "application/octet-stream"
}


@app.get("/")
def home():
    return {
        "app": "MJR Downloader Backend",
        "status": "online"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/process")
async def process_media(
    file: UploadFile = File(...),
    format: str = Query(..., pattern="^(mp3|mp4)$")
):
    content_type = (file.content_type or "").lower()

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported media type"
        )

    temp_dir = tempfile.mkdtemp(prefix="mjr_")
    input_path = Path(temp_dir) / "input"
    output_path = Path(temp_dir) / (
        "download.mp3" if format == "mp3"
        else "download.mp4"
    )

    try:
        size = 0

        with open(input_path, "wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                size += len(chunk)

                if size > MAX_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="File exceeds 50 MB limit"
                    )

                output.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=400,
                detail="Empty file"
            )

        if format == "mp4":
            if content_type not in (
                "video/mp4",
                "video/quicktime",
                "application/octet-stream"
            ):
                raise HTTPException(
                    status_code=415,
                    detail="Please upload a video file"
                )

            os.replace(input_path, output_path)

        else:
            command = [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-i", str(input_path),
                "-vn",
                "-codec:a", "libmp3lame",
                "-b:a", "192k",
                str(output_path)
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                timeout=180
            )

            if result.returncode != 0:
                raise HTTPException(
                    status_code=422,
                    detail="Audio conversion failed"
                )

        if not output_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Output file was not created"
            )

        def cleanup():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        return FileResponse(
            path=str(output_path),
            filename=f"MJR_Download.{format}",
            media_type=(
                "audio/mpeg" if format == "mp3"
                else "video/mp4"
            ),
            background=BackgroundTask(cleanup)
        )

    except HTTPException:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    except subprocess.TimeoutExpired:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=408,
            detail="Conversion timed out"
        )

    except Exception:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail="Processing failed"
        )

    finally:
        await file.close()
