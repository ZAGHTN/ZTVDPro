"""Tests unitaires pour app/downloader.py."""
from __future__ import annotations

import pytest

from app.downloader import (
    REMOTE_COMPONENTS,
    SUPPORTED_DOMAINS,
    DownloadWorker,
    DownloaderError,
    InvalidURLError,
    _YdlLogger,
    build_analysis_options,
    build_options,
    clean,
    is_valid_url,
    js_runtime_options,
    summarize_info,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "HTTPS://WWW.YOUTUBE.COM/watch?v=dQw4w9WgXcQ",
        "http://youtube.com/watch?v=x",
        "https://youtube.com:443/watch?v=x",
        "https://www.facebook.com/reel/4303958736547434",
        "https://m.facebook.com/watch/?v=1883051732862019",
        "https://www.dailymotion.com/video/xbrfctm",
    ],
)
def test_is_valid_url_accepts_supported_domains(url: str) -> None:
    assert is_valid_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "not-a-url",
        "ftp://youtube.com/watch?v=x",
        "https://example.com/video.mp4",
        "https://notyoutube.com/watch?v=x",
        "https://youtube.com.evil.com/watch?v=x",
        "https://evil.com/?next=https://youtube.com",
        "https://evil.com/#youtube.com",
        "https://youtube.com@evil.com/watch?v=x",
        "https://evil.com\\@youtube.com/watch?v=x",
        "https://youtube.com:notaport/watch?v=x",
        "https:///watch?v=x",
    ],
)
def test_is_valid_url_rejects_unsupported_or_spoofed_urls(url: str) -> None:
    assert not is_valid_url(url)


def test_supported_domains_are_documented() -> None:
    assert SUPPORTED_DOMAINS == (
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "dailymotion.com",
    )


def test_custom_exceptions() -> None:
    err = InvalidURLError("URL invalide")
    assert isinstance(err, DownloaderError)
    assert str(err) == "URL invalide"


def test_clean_removes_ansi_sequences() -> None:
    assert clean("\x1b[31merreur\x1b[0m") == "erreur"


def test_ydl_logger_emits_clean_messages() -> None:
    received: list[str] = []
    ydl_logger = _YdlLogger(received.append)

    ydl_logger.debug("\x1b[32mdebug\x1b[0m")
    ydl_logger.info("info")
    ydl_logger.warning("warning")
    ydl_logger.error("error")

    assert received == ["debug", "info", "warning", "error"]


def test_ydl_logger_deduplicates_consecutive_messages() -> None:
    received: list[str] = []
    ydl_logger = _YdlLogger(received.append)

    ydl_logger.debug("même message")
    ydl_logger.debug("même message")
    ydl_logger.debug("autre message")

    assert received == ["même message", "autre message"]


def test_ydl_logger_without_callback_does_not_raise() -> None:
    _YdlLogger().debug("message ignoré par l'interface")


def test_build_analysis_options_passes_ffmpeg_location() -> None:
    opts = build_analysis_options("/opt/ffmpeg")

    assert opts["ffmpeg_location"] == "/opt/ffmpeg"
    assert opts["skip_download"] is True
    assert opts["http_headers"]["User-Agent"].startswith("Mozilla/5.0")


def test_build_analysis_options_without_ffmpeg_location() -> None:
    assert "ffmpeg_location" not in build_analysis_options(None)


def test_builders_allow_official_ejs_solver() -> None:
    assert REMOTE_COMPONENTS == ("ejs:github",)
    assert build_analysis_options(None)["remote_components"] == ["ejs:github"]
    assert build_options("/tmp/sortie", 1080, "mp4", None)["remote_components"] == ["ejs:github"]
    assert build_options("/tmp/sortie", 0, "mp3", None)["remote_components"] == ["ejs:github"]


def test_js_runtime_options_uses_bundled_deno(monkeypatch) -> None:
    monkeypatch.setattr("app.downloader.bundled_deno_path", lambda: r"C:\deno\deno.exe")
    monkeypatch.setattr("app.downloader.shutil.which", lambda name: None)

    assert js_runtime_options() == {
        "js_runtimes": {"deno": {"path": r"C:\deno\deno.exe"}},
    }


def test_js_runtime_options_uses_system_deno(monkeypatch) -> None:
    monkeypatch.setattr("app.downloader.bundled_deno_path", lambda: None)
    monkeypatch.setattr(
        "app.downloader.shutil.which",
        lambda name: r"C:\deno\deno.exe" if name == "deno" else None,
    )

    assert js_runtime_options() == {"js_runtimes": {"deno": {}}}


def test_js_runtime_options_falls_back_to_node(monkeypatch) -> None:
    monkeypatch.setattr("app.downloader.bundled_deno_path", lambda: None)
    monkeypatch.setattr(
        "app.downloader.shutil.which",
        lambda name: r"C:\node\node.exe" if name == "node" else None,
    )

    assert js_runtime_options() == {"js_runtimes": {"node": {}}}


def test_js_runtime_options_without_runtime(monkeypatch) -> None:
    monkeypatch.setattr("app.downloader.bundled_deno_path", lambda: None)
    monkeypatch.setattr("app.downloader.shutil.which", lambda name: None)

    assert js_runtime_options() == {}


def test_builders_include_js_runtime_configuration(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.downloader.js_runtime_options",
        lambda: {"js_runtimes": {"deno": {"path": "/deno"}}},
    )

    assert build_analysis_options(None)["js_runtimes"] == {"deno": {"path": "/deno"}}
    assert build_options("/tmp/sortie", 1080, "mp4", None)["js_runtimes"] == {
        "deno": {"path": "/deno"},
    }


def test_build_options_video_prefers_http_headers() -> None:
    opts = build_options("/tmp/sortie", 1080, "mp4", None)

    assert opts["paths"] == {"home": "/tmp/sortie"}
    assert "User-Agent" not in opts
    assert opts["http_headers"]["User-Agent"].startswith("Mozilla/5.0")
    assert "[height<=1080]" in opts["format"]
    assert opts["merge_output_format"] == "mp4"
    assert any(pp["key"] == "FFmpegVideoRemuxer" for pp in opts["postprocessors"])
    assert any(pp["key"] == "FFmpegMetadata" for pp in opts["postprocessors"])


def test_build_options_audio() -> None:
    opts = build_options("/tmp/sortie", 0, "mp3", "/opt/ffmpeg")

    assert opts["format"] == "bestaudio/best"
    assert opts["ffmpeg_location"] == "/opt/ffmpeg"
    assert any(pp["key"] == "FFmpegExtractAudio" for pp in opts["postprocessors"])
    assert "merge_output_format" not in opts


def test_summarize_info_uses_first_playlist_entry() -> None:
    info = {
        "_type": "playlist",
        "entries": [
            None,
            {
                "title": "Vidéo",
                "uploader": "Chaîne",
                "duration": 90,
                "formats": [
                    {"height": 2160, "vcodec": "av01"},
                    {"height": 1080, "vcodec": "avc1"},
                    {"height": 0, "vcodec": "none", "acodec": "opus"},
                ],
            },
        ],
    }

    summary = summarize_info(info)

    assert summary["title"] == "Vidéo"
    assert summary["uploader"] == "Chaîne"
    assert summary["duration"] == 90
    assert summary["max_height"] == 2160
    assert summary["is_live"] is False


def test_summarize_info_audio_only_has_no_video_height() -> None:
    info = {
        "title": "Audio",
        "formats": [{"height": None, "vcodec": "none", "acodec": "opus"}],
    }

    assert summarize_info(info)["max_height"] == 0


def test_download_worker_falls_back_to_mkv_after_webm_failure(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run_once(self, container: str) -> str:
        calls.append(container)
        if container == "webm":
            raise DownloaderError("merge failed")
        return "/tmp/sortie.mkv"

    monkeypatch.setattr(DownloadWorker, "_run_once", fake_run_once)
    worker = DownloadWorker("https://youtube.com/watch?v=x", "/tmp", 1080, "webm", None)
    steps: list[str] = []
    succeeded: list[str] = []
    worker.step.connect(lambda key, _params: steps.append(key))
    worker.succeeded.connect(succeeded.append)

    worker.run()

    assert calls == ["webm", "mkv"]
    assert steps.count("step_fallback_mkv") == 1
    assert succeeded == ["/tmp/sortie.mkv"]


def test_download_worker_does_not_fall_back_for_other_containers(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run_once(self, container: str) -> str:
        calls.append(container)
        raise DownloaderError("boom")

    monkeypatch.setattr(DownloadWorker, "_run_once", fake_run_once)
    worker = DownloadWorker("https://youtube.com/watch?v=x", "/tmp", 1080, "mp4", None)
    failures: list[str] = []
    worker.failed.connect(failures.append)

    worker.run()

    assert calls == ["mp4"]
    assert failures == ["boom"]


def test_download_worker_fallback_is_attempted_only_once(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run_once(self, container: str) -> str:
        calls.append(container)
        raise DownloaderError(f"{container} failed")

    monkeypatch.setattr(DownloadWorker, "_run_once", fake_run_once)
    worker = DownloadWorker("https://youtube.com/watch?v=x", "/tmp", 1080, "webm", None)
    failures: list[str] = []
    worker.failed.connect(failures.append)

    worker.run()

    assert calls == ["webm", "mkv"]
    assert failures == ["mkv failed"]


def test_download_worker_does_not_fallback_on_network_error(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run_once(self, container: str) -> str:
        calls.append(container)
        raise DownloaderError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(DownloadWorker, "_run_once", fake_run_once)
    worker = DownloadWorker("https://youtube.com/watch?v=x", "/tmp", 1080, "webm", None)
    failures: list[str] = []
    worker.failed.connect(failures.append)

    worker.run()

    assert calls == ["webm"]
    assert failures == ["HTTP Error 403: Forbidden"]


def test_download_worker_does_not_fallback_when_cancelled(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run_once(self, container: str) -> str:
        calls.append(container)
        raise DownloaderError("interrupted")

    monkeypatch.setattr(DownloadWorker, "_run_once", fake_run_once)
    worker = DownloadWorker("https://youtube.com/watch?v=x", "/tmp", 1080, "webm", None)
    cancelled: list[bool] = []
    worker.cancelled.connect(lambda: cancelled.append(True))
    worker.cancel()

    worker.run()

    assert calls == ["webm"]
    assert cancelled == [True]
