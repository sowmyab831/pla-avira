"""GPU/CUDA utilities for model inference"""
import torch
import logging

logger = logging.getLogger(__name__)


def get_device():
    """
    Get the best available device for inference.
    Priority: CUDA > CPU
    """
    if torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info(f"✓ CUDA available. Using GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"  CUDA Version: {torch.version.cuda}")
        logger.info(f"  GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        return device
    else:
        device = torch.device("cpu")
        logger.info("⚠ CUDA not available. Falling back to CPU")
        return device


def get_device_map():
    """Get device map for model loading"""
    device = get_device()
    if device.type == "cuda":
        return "auto"  # Let transformers handle device mapping
    return "cpu"


def optimize_for_device(model, device):
    """Optimize model for the target device"""
    model = model.to(device)
    
    if device.type == "cuda":
        # Enable mixed precision for faster inference on GPU
        model.half()
        logger.info("✓ Mixed precision enabled for GPU inference")
    
    return model


def log_gpu_stats():
    """Log GPU memory statistics"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1e9
        reserved = torch.cuda.memory_reserved() / 1e9
        total = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"GPU Memory - Allocated: {allocated:.2f}GB, Reserved: {reserved:.2f}GB, Total: {total:.2f}GB")
