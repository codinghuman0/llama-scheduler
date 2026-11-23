import os

import pytest

from utils import ServerPreset


def make_server():
    server = ServerPreset.tinyllama2()
    model_path = os.environ.get("LLAMA_SERVER_TEST_MODEL")
    if model_path:
        server.model_file = model_path
        server.model_hf_repo = None
        server.model_hf_file = None
    return server


@pytest.mark.parametrize("profile_mode", ["legacy", "auto", "phase"])
def test_compute_profile_modes_completion(profile_mode: str):
    server = make_server()
    server.server_compute_profile_mode = profile_mode
    server.n_threads = 2
    server.n_threads_batch = 4
    server.temperature = 0.0
    server.seed = 42
    server.start()
    try:
        response = server.make_request("POST", "/completion", data={
            "prompt": "I believe the meaning of life is",
            "n_predict": 8,
            "cache_prompt": False,
            "return_tokens": True,
            "seed": 42,
            "temperature": 0.0,
        })

        assert response.status_code == 200
        assert response.body["stop_type"] == "limit"
        assert response.body["timings"]["predicted_n"] == 8
        assert len(response.body["tokens"]) == 8
    finally:
        server.stop()


def test_phase_compute_profile_mode_streaming():
    server = make_server()
    server.server_compute_profile_mode = "phase"
    server.n_threads = 2
    server.n_threads_batch = 4
    server.temperature = 0.0
    server.seed = 42
    server.start()
    try:
        events = list(server.make_stream_request("POST", "/completion", data={
            "prompt": "I believe the meaning of life is",
            "n_predict": 8,
            "cache_prompt": False,
            "ignore_eos": True,
            "return_tokens": True,
            "seed": 42,
            "stream": True,
            "temperature": 0.0,
        }))

        tokens = [token for event in events if not event["stop"] for token in event["tokens"]]
        assert len(tokens) == 8
        assert events[-1]["stop"]
        assert events[-1]["stop_type"] == "limit"
    finally:
        server.stop()
