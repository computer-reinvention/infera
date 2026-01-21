# ML Model Inference

## Overview
ML inference deployment serves trained machine learning models for predictions in production. Modern platforms offer serverless options that scale automatically and handle model versioning, A/B testing, and monitoring.

**Use when:**
- Deploying trained ML models for predictions
- Need auto-scaling based on inference traffic
- Require model versioning and A/B testing
- GPU acceleration needed for inference
- Real-time or batch predictions

**Don't use when:**
- Simple rule-based logic suffices
- Training workloads (use training platforms)
- Edge inference only (use TensorFlow Lite/ONNX)

## Detection Signals

```
Files:
- model.pkl, model.pt, model.onnx
- requirements.txt with ml libraries
- Dockerfile with CUDA
- serving/, inference/

Dependencies:
- tensorflow, torch, transformers
- scikit-learn, xgboost
- onnxruntime, triton
- fastapi, flask (for serving)

Code Patterns:
- model.predict(), model()
- torch.load(), tf.saved_model
- @app.post("/predict")
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   ML Inference Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      Clients                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │   Web App   │  │  Mobile App │  │  Batch Job  │      │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │   │
│  └─────────┼────────────────┼────────────────┼──────────────┘   │
│            └────────────────┼────────────────┘                   │
│                             │ /predict                           │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                    API Gateway / LB                       │   │
│  │            (Traffic splitting for A/B testing)            │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                   Inference Servers                       │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │             Model Serving Container                  │ │   │
│  │  │  ┌───────────────────────────────────────────────┐  │ │   │
│  │  │  │  FastAPI / Flask / TorchServe / TF Serving    │  │ │   │
│  │  │  │                                               │  │ │   │
│  │  │  │  ┌─────────────┐  ┌─────────────────────────┐ │  │ │   │
│  │  │  │  │   Model     │  │   Preprocessing         │ │  │ │   │
│  │  │  │  │  (GPU/CPU)  │  │   Postprocessing        │ │  │ │   │
│  │  │  │  └─────────────┘  └─────────────────────────┘ │  │ │   │
│  │  │  └───────────────────────────────────────────────┘  │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                    Model Storage                          │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │   │
│  │  │ Model v1 │  │ Model v2 │  │ Model v3 │               │   │
│  │  │ (50%)    │  │ (50%)    │  │ (shadow) │               │   │
│  │  └──────────┘  └──────────┘  └──────────┘               │   │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Provider Comparison

| Feature | Vertex AI | SageMaker | Cloud Run | Replicate |
|---------|-----------|-----------|-----------|-----------|
| **GPU Support** | Yes | Yes | No | Yes |
| **Auto-scaling** | Yes | Yes | Yes | Yes |
| **Model Registry** | Built-in | Built-in | External | Built-in |
| **A/B Testing** | Built-in | Built-in | Manual | No |
| **Serverless** | Yes | Yes | Yes | Yes |
| **Cold Start** | ~30-60s | ~30-60s | ~1-5s (CPU) | ~5-30s |

## FastAPI Model Server

### Basic Implementation

```python
# server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import numpy as np
from typing import List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ML Inference API")

# Global model
model = None
device = None

class PredictRequest(BaseModel):
    features: List[float]

class PredictResponse(BaseModel):
    prediction: float
    confidence: float

@app.on_event("startup")
async def load_model():
    global model, device

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    # Load model
    model = torch.jit.load("model.pt", map_location=device)
    model.eval()

    logger.info("Model loaded successfully")

@app.get("/health")
async def health():
    return {"status": "healthy", "model_loaded": model is not None}

@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Preprocess
        features = torch.tensor([request.features], dtype=torch.float32).to(device)

        # Inference
        with torch.no_grad():
            output = model(features)
            probabilities = torch.softmax(output, dim=1)
            prediction = torch.argmax(probabilities, dim=1).item()
            confidence = probabilities[0][prediction].item()

        return PredictResponse(
            prediction=prediction,
            confidence=confidence
        )

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict/batch")
async def predict_batch(requests: List[PredictRequest]):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Batch preprocessing
        features = torch.tensor(
            [r.features for r in requests],
            dtype=torch.float32
        ).to(device)

        # Batch inference
        with torch.no_grad():
            outputs = model(features)
            probabilities = torch.softmax(outputs, dim=1)
            predictions = torch.argmax(probabilities, dim=1).tolist()
            confidences = [probabilities[i][p].item() for i, p in enumerate(predictions)]

        return [
            PredictResponse(prediction=p, confidence=c)
            for p, c in zip(predictions, confidences)
        ]

    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy model and code
COPY model.pt .
COPY server.py .

# Run server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
```

### GPU Dockerfile

```dockerfile
# Dockerfile.gpu
FROM nvidia/cuda:11.8-cudnn8-runtime-ubuntu22.04

WORKDIR /app

# Install Python
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy model and code
COPY model.pt .
COPY server.py .

# Run server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
```

## GCP Vertex AI

### Terraform Configuration

```hcl
# vertex_ai.tf

# Upload model to Cloud Storage
resource "google_storage_bucket" "models" {
  name     = "${var.project_name}-models"
  location = var.region

  uniform_bucket_level_access = true
}

# Vertex AI Model
resource "google_vertex_ai_model" "main" {
  display_name = "${var.project_name}-model"
  region       = var.region

  container_spec {
    image_uri = "${var.region}-docker.pkg.dev/${var.project_id}/${var.project_name}/model-server:latest"

    predict_route = "/predict"
    health_route  = "/health"

    ports {
      container_port = 8080
    }

    env {
      name  = "MODEL_PATH"
      value = "gs://${google_storage_bucket.models.name}/models/v1"
    }
  }

  artifact_uri = "gs://${google_storage_bucket.models.name}/artifacts"
}

# Vertex AI Endpoint
resource "google_vertex_ai_endpoint" "main" {
  name         = "${var.project_name}-endpoint"
  display_name = "${var.project_name} Inference Endpoint"
  location     = var.region

  network = "projects/${var.project_id}/global/networks/${google_compute_network.vpc.name}"
}

# Deploy model to endpoint
resource "google_vertex_ai_endpoint_deployed_model" "main" {
  endpoint = google_vertex_ai_endpoint.main.id
  model    = google_vertex_ai_model.main.id

  display_name = "v1"

  dedicated_resources {
    machine_spec {
      machine_type      = "n1-standard-4"
      accelerator_type  = "NVIDIA_TESLA_T4"
      accelerator_count = 1
    }
    min_replica_count = 1
    max_replica_count = 5

    autoscaling_metric_specs {
      metric_name   = "aiplatform.googleapis.com/prediction/online/cpu/utilization"
      target        = 60
    }
  }

  traffic_split = {
    "0" = 100
  }
}
```

### Vertex AI Client

```python
# vertex_client.py
from google.cloud import aiplatform

aiplatform.init(project="my-project", location="us-central1")

endpoint = aiplatform.Endpoint("projects/my-project/locations/us-central1/endpoints/123456")

# Single prediction
response = endpoint.predict(instances=[{"features": [1.0, 2.0, 3.0]}])
print(response.predictions)

# Batch prediction
job = aiplatform.BatchPredictionJob.create(
    job_display_name="batch-predict",
    model_name="projects/my-project/locations/us-central1/models/789",
    instances_format="jsonl",
    predictions_format="jsonl",
    gcs_source="gs://my-bucket/input.jsonl",
    gcs_destination_prefix="gs://my-bucket/output/",
    machine_type="n1-standard-4",
    accelerator_type="NVIDIA_TESLA_T4",
    accelerator_count=1,
)
```

## AWS SageMaker

### Terraform Configuration

```hcl
# sagemaker.tf

# S3 bucket for models
resource "aws_s3_bucket" "models" {
  bucket = "${var.project_name}-models"
}

# SageMaker Model
resource "aws_sagemaker_model" "main" {
  name               = "${var.project_name}-model"
  execution_role_arn = aws_iam_role.sagemaker.arn

  primary_container {
    image          = "${aws_ecr_repository.model.repository_url}:latest"
    model_data_url = "s3://${aws_s3_bucket.models.bucket}/models/model.tar.gz"

    environment = {
      SAGEMAKER_PROGRAM = "inference.py"
    }
  }
}

# SageMaker Endpoint Configuration
resource "aws_sagemaker_endpoint_configuration" "main" {
  name = "${var.project_name}-config"

  production_variants {
    variant_name           = "primary"
    model_name             = aws_sagemaker_model.main.name
    initial_instance_count = 1
    instance_type          = "ml.g4dn.xlarge"  # GPU instance

    serverless_config {
      max_concurrency         = 10
      memory_size_in_mb       = 4096
    }
  }

  # A/B testing with traffic split
  production_variants {
    variant_name           = "canary"
    model_name             = aws_sagemaker_model.canary.name
    initial_variant_weight = 10  # 10% traffic
    instance_type          = "ml.g4dn.xlarge"
  }
}

# SageMaker Endpoint
resource "aws_sagemaker_endpoint" "main" {
  name                 = "${var.project_name}-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.main.name
}

# Auto-scaling
resource "aws_appautoscaling_target" "sagemaker" {
  max_capacity       = 10
  min_capacity       = 1
  resource_id        = "endpoint/${aws_sagemaker_endpoint.main.name}/variant/primary"
  scalable_dimension = "sagemaker:variant:DesiredInstanceCount"
  service_namespace  = "sagemaker"
}

resource "aws_appautoscaling_policy" "sagemaker" {
  name               = "${var.project_name}-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.sagemaker.resource_id
  scalable_dimension = aws_appautoscaling_target.sagemaker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.sagemaker.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "SageMakerVariantInvocationsPerInstance"
    }
    target_value = 100
  }
}
```

## Hugging Face Transformers

```python
# transformers_server.py
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer
import torch

app = FastAPI()

# Load model on startup
model_name = "distilbert-base-uncased-finetuned-sst-2-english"
device = 0 if torch.cuda.is_available() else -1

# Using pipeline (simpler)
classifier = pipeline("sentiment-analysis", model=model_name, device=device)

# Or manual loading (more control)
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)
if torch.cuda.is_available():
    model = model.cuda()
model.eval()

class TextRequest(BaseModel):
    text: str

class SentimentResponse(BaseModel):
    label: str
    score: float

@app.post("/predict", response_model=SentimentResponse)
async def predict(request: TextRequest):
    # Using pipeline
    result = classifier(request.text)[0]
    return SentimentResponse(label=result["label"], score=result["score"])

@app.post("/predict/batch")
async def predict_batch(texts: list[str]):
    results = classifier(texts)
    return [SentimentResponse(label=r["label"], score=r["score"]) for r in results]

# Manual inference with more control
@app.post("/predict/manual")
async def predict_manual(request: TextRequest):
    inputs = tokenizer(request.text, return_tensors="pt", truncation=True, max_length=512)
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1)
        prediction = torch.argmax(probs, dim=1).item()
        confidence = probs[0][prediction].item()

    labels = ["NEGATIVE", "POSITIVE"]
    return SentimentResponse(label=labels[prediction], score=confidence)
```

## Replicate / RunPod (Serverless GPU)

```python
# replicate_client.py
import replicate

# Run inference
output = replicate.run(
    "stability-ai/stable-diffusion:db21e45d3f7023abc2a46ee38a23973f6dce16bb082a930b0c49861f96d1e5bf",
    input={"prompt": "a photo of a cat"}
)

# Deploy custom model
# cog.yaml
"""
build:
  python_version: "3.11"
  python_packages:
    - torch==2.0.0
    - transformers==4.30.0

predict: "predict.py:Predictor"
"""

# predict.py
from cog import BasePredictor, Input
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

class Predictor(BasePredictor):
    def setup(self):
        self.tokenizer = AutoTokenizer.from_pretrained("gpt2")
        self.model = AutoModelForCausalLM.from_pretrained("gpt2")
        if torch.cuda.is_available():
            self.model = self.model.cuda()

    def predict(
        self,
        prompt: str = Input(description="Input prompt"),
        max_length: int = Input(default=100, ge=1, le=500),
    ) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        outputs = self.model.generate(**inputs, max_length=max_length)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
```

## Cost Breakdown

| Provider | GPU Type | On-Demand | Serverless |
|----------|----------|-----------|------------|
| **Vertex AI** | T4 | $0.35/hr | $0.40/hr |
| **SageMaker** | g4dn.xlarge | $0.736/hr | Pay per request |
| **Cloud Run** | CPU only | $0.00002/vCPU-s | - |
| **Replicate** | A40 | - | $0.00115/sec |
| **RunPod** | A100 | $1.89/hr | $0.00031/sec |

## Best Practices

### Model Optimization

```python
# Quantization for faster inference
import torch

# Dynamic quantization
model_quantized = torch.quantization.quantize_dynamic(
    model, {torch.nn.Linear}, dtype=torch.qint8
)

# ONNX export for cross-platform
torch.onnx.export(
    model,
    dummy_input,
    "model.onnx",
    opset_version=14,
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
)

# TensorRT optimization (NVIDIA GPUs)
import tensorrt as trt
# ... optimization code
```

### Batching

```python
import asyncio
from collections import deque

class BatchProcessor:
    def __init__(self, model, batch_size=32, timeout=0.1):
        self.model = model
        self.batch_size = batch_size
        self.timeout = timeout
        self.queue = deque()
        self.lock = asyncio.Lock()

    async def predict(self, input_data):
        future = asyncio.Future()
        async with self.lock:
            self.queue.append((input_data, future))

        # Trigger batch processing
        asyncio.create_task(self._process_batch())

        return await future

    async def _process_batch(self):
        await asyncio.sleep(self.timeout)

        async with self.lock:
            if not self.queue:
                return

            batch = []
            futures = []
            while self.queue and len(batch) < self.batch_size:
                input_data, future = self.queue.popleft()
                batch.append(input_data)
                futures.append(future)

        # Process batch
        results = self.model.predict_batch(batch)

        for future, result in zip(futures, results):
            future.set_result(result)
```

## Common Mistakes

1. **No model warmup** - First request is slow
2. **Loading model per request** - Should load once on startup
3. **Missing health checks** - Unhealthy instances receive traffic
4. **No batching** - Inefficient GPU utilization
5. **Synchronous inference** - Blocks event loop
6. **Missing input validation** - Crashes on bad input
7. **No model versioning** - Can't rollback
8. **Ignoring cold starts** - Users experience latency
9. **No monitoring** - Can't detect model drift
10. **Over-provisioning** - Wasting GPU resources

## Example Configuration

```yaml
# infera.yaml
project_name: ml-service
provider: gcp
region: us-central1

ml_inference:
  model:
    name: sentiment-classifier
    framework: pytorch
    path: gs://my-bucket/models/v1

  serving:
    runtime: vertex_ai
    machine_type: n1-standard-4
    accelerator: NVIDIA_TESLA_T4
    accelerator_count: 1

  scaling:
    min_replicas: 1
    max_replicas: 10
    target_cpu_utilization: 60

  endpoints:
    production:
      traffic_split:
        v1: 90
        v2: 10  # Canary

monitoring:
  enable_prediction_logging: true
  alert_on_latency_p99: 500ms
```

## Sources

- [Vertex AI Prediction](https://cloud.google.com/vertex-ai/docs/predictions/overview)
- [SageMaker Inference](https://docs.aws.amazon.com/sagemaker/latest/dg/deploy-model.html)
- [TorchServe](https://pytorch.org/serve/)
- [Hugging Face Inference](https://huggingface.co/docs/transformers/main_classes/pipelines)
- [Replicate Documentation](https://replicate.com/docs)
- [ONNX Runtime](https://onnxruntime.ai/docs/)
