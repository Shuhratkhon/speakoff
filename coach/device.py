"""Use a GPU (NVIDIA, CUDA) automatically when the server has one; otherwise the CPU.
Whisper, the grammar model and the pronunciation model run ~10x faster on a GPU. Nothing else changes."""

import torch

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
