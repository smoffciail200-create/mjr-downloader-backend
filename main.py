import os
import tempfile
import subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

app = FastAPI(
    title="MJR TikTok Downloader API",
    description="TikTok Video & Audio Downloader Service",
    version="2.0.0"
)

@app.get("/")
def home():
    return {
        "app": "MJR Downloader Backend",
        "status": "online"
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/download")
async def download_tiktok(
    url: str = Query(..., description="TikTok video URL"),
    format: str = Query(..., pattern="^(mp3|mp4)$", description="Download format: mp3 or mp4")
):
    temp_dir = tempfile.mkdtemp(prefix="mjr_tiktok_")
    output_template = str(Path(temp_dir) / "output.%(ext)s")

    try:
        # yt-dlp কমান্ড দিয়ে টিকটক ভিডিও ডাউনলোড করা
        cmd = [
            "yt-dlp",
            "-o", output_template,
            "--no-check-certificates",
            url
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail="Failed to download video from TikTok link. Please check the URL."
            )

        # ডাউনলোড হওয়া ফাইলটি খুঁজে বের করা
        downloaded_files = list(Path(temp_dir).glob("output.*"))
        if not downloaded_files:
            raise HTTPException(
                status_code=500,
                detail="Downloaded file not found"
            )

        raw_file = downloaded_files[0]
        final_output = Path(temp_dir) / ("download.mp3" if format == "mp3" else "download.mp4")

        # যদি ফরম্যাট mp3 চায়, তবে ffmpeg দিয়ে অডিও কনভার্ট করা
        if format == "mp3":
            conversion_cmd = [
                "ffmpeg",
                "-y",
                "-i", str(raw_file),
                "-vn",
                "-codec:a", "libmp3lame",
                "-b:a", "192k",
                str(final_output)
            ]
            conv_result = subprocess.run(conversion_cmd, capture_output=True, timeout=120)
            if conv_result.returncode != 0:
                raise HTTPException(
                    status_code=422,
                    detail="Audio conversion failed"
                )
        else:
            # mp4 চাইলে সরাসরি ফাইল রিনেম বা মুভ করা
            if raw_file != final_output:
                os.replace(raw_file, final_output)

        if not final_output.exists():
            raise HTTPException(
                status_code=500,
                detail="Final output file was not created"
            )

        def cleanup():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        return FileResponse(
            path=str(final_output),
            filename=f"MJR_TikTok.{format}",
            media_type="audio/mpeg" if format == "mp3" else "video/mp4",
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
            detail="Process timed out"
        )

    except Exception as e:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
