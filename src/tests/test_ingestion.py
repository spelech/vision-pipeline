import os
import sys
import io
import json
import base64
from PIL import Image
import requests
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.base import BasePipeline

def test_pipeline_logic():
    print("--- Testing Pipeline Logic ---")
    # Using DefaultPipeline instead of the non-existent VisionPipeline
    from pipelines.default import DefaultPipeline
    pipeline = DefaultPipeline()
    
    # Create a dummy image
    img = Image.new('RGB', (100, 100), color = (73, 109, 137))
    
    try:
        print("Running pipeline on dummy image...")
        results = pipeline.run_pipeline(img, text_description="test item blue box")
        print("Pipeline run successful.")
        print(f"Product Name: {results['llm_output'].get('product_name')}")
        print(f"Duplicates found: {json.dumps(results['duplicates'], indent=2)}")
        
        # Verify schema
        assert "mealie" in results["duplicates"]
        assert "recipes" in results["duplicates"]["mealie"]
        assert "foods" in results["duplicates"]["mealie"]
        print("✅ Schema verification passed.")
        
    except Exception as e:
        print(f"❌ Pipeline logic failed: {e}")
        import traceback
        traceback.print_exc()

def test_api_endpoint():
    print("\n--- Testing API Endpoint ---")
    # Note: Assumes the container is running or we test against localhost if running locally
    url = "http://localhost:8501/identify"
    
    # Create a dummy image
    img = Image.new('RGB', (100, 100), color = (73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    img_bytes = buf.getvalue()
    
    try:
        print(f"Sending POST request to {url}...")
        files = {'file': ('test.jpg', img_bytes, 'image/jpeg')}
        data = {'text': 'test item via API', 'rotation': 0, 'mirror': False}
        
        response = requests.post(url, files=files, data=data, timeout=30)
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("success"):
                print("✅ API identification successful.")
                print(f"AI Preview Length: {len(res_json.get('ai_preview', ''))}")
            else:
                print(f"❌ API returned success=False: {res_json.get('error')}")
        else:
            print(f"❌ API returned error status: {response.text}")
            
    except Exception as e:
        print(f"❌ API test failed: {e}")

if __name__ == "__main__":
    load_dotenv()
    # We can't easily run the API test against the container from here if it's on a different network,
    # but we can test the pipeline logic directly.
    test_pipeline_logic()
    # If you want to test the full API, ensure the server is running on the host or in the container.
    # test_api_endpoint()
