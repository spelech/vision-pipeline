import os
import json
from pipeline import VisionPipeline
from PIL import Image

def test_description_only():
    print("Testing with description only...")
    vp = VisionPipeline()
    descriptions = [
        "A bottle of Huy Fong Sriracha 28oz",
        "A green box of tea with a picture of a bear on it, maybe 20 tea bags",
        "Small plastic bag of white powder labeled 'Baking Soda' from Arm & Hammer"
    ]
    for desc in descriptions:
        print(f"\n--- Testing: {desc} ---")
        result = vp.run_pipeline(text_description=desc)
        print(f"Enriched Search Query: {result.get('searxng_query')}")
        print(json.dumps(result['llm_output'], indent=2))

def test_with_image_if_exists(path):
    if os.path.exists(path):
        print(f"Testing with image: {path}")
        image = Image.open(path)
        vp = VisionPipeline()
        result = vp.run_pipeline(image=image)
        print(json.dumps(result, indent=2))
    else:
        print(f"Image not found at {path}")

def test_model_comparison():
    print("\nTesting Model Comparison...")
    vp = VisionPipeline()
    desc = "A green box of tea with a picture of a bear on it"
    models = ["qwen/qwen3-vl-32b-instruct"]
    
    for m in models:
        print(f"\n--- Model: {m} ---")
        result = vp.run_pipeline(text_description=desc, model=m)
        print(json.dumps(result['llm_output'], indent=2))

if __name__ == "__main__":
    test_description_only()
    test_model_comparison()
