import os
import unittest
import json
from app import app

class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = 'test_uploads'
        os.makedirs('test_uploads', exist_ok=True)

    def tearDown(self):
        # Cleanup
        for f in os.listdir('test_uploads'):
            os.remove(os.path.join('test_uploads', f))
        os.rmdir('test_uploads')

    def test_homepage(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'CI/CD Pipeline Optimizer', response.data)

    def test_upload_flow(self):
        # Create a dummy json file
        data = {
            "jobs": [
                {"name": "test-job", "duration_seconds": 20}
            ]
        }
        
        # Simulate file upload
        import io
        response = self.client.post('/upload', data={
            'file': (io.BytesIO(json.dumps(data).encode('utf-8')), 'test_log.json')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'test-job', response.data)
        self.assertIn(b'Optimization Suggestions', response.data) 

    def test_upload_mixed_format(self):
        data = {
            "jobs": [
                {"name": "legacy-job", "duration": 45}, # Uses 'duration'
                {"name": "modern-job", "duration_seconds": 10}
            ]
        }
        import io
        response = self.client.post('/upload', data={
            'file': (io.BytesIO(json.dumps(data).encode('utf-8')), 'mixed.json')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'legacy-job', response.data)
        self.assertIn(b'55.0s', response.data) # Total duration

    def test_upload_invalid_json(self):
        import io
        response = self.client.post('/upload', data={
            'file': (io.BytesIO(b'{invalid-json'), 'bad.json')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid JSON file', response.data)
        
    def test_upload_invalid_schema(self):
        data = {"wrong_field": "no_jobs"}
        import io
        response = self.client.post('/upload', data={
            'file': (io.BytesIO(json.dumps(data).encode('utf-8')), 'schema.json')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid Log Format', response.data) 

if __name__ == '__main__':
    unittest.main()
