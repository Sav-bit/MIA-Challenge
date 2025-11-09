#!/bin/bash
# Test script for the Dice Score API

echo "================================"
echo "Dice Score API Test Script"
echo "================================"
echo ""

# Create a test NIfTI file
echo "Creating test NIfTI file..."
python << 'EOF'
import nibabel as nib
import numpy as np

# Create a test file that matches the reference dimensions (10x10x10)
data = np.random.randint(0, 2, size=(10, 10, 10)).astype(np.float32)
img = nib.Nifti1Image(data, affine=np.eye(4))
nib.save(img, '/tmp/test_submission.nii.gz')
print("✓ Test file created")
EOF

echo ""
echo "Starting Django server..."
python manage.py runserver 8000 > /dev/null 2>&1 &
SERVER_PID=$!
sleep 3
echo "✓ Server started (PID: $SERVER_PID)"

echo ""
echo "Testing API endpoints..."
echo ""

# Test 1: Valid submission
echo "Test 1: Valid submission"
RESPONSE=$(curl -s -X POST http://localhost:8000/api/dice/calculate/ \
  -F "file=@/tmp/test_submission.nii.gz" \
  -F "name=TestGroup" \
  -w "\n%{http_code}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Status: 200 OK"
    echo "  Response: $BODY"
else
    echo "✗ Status: $HTTP_CODE"
    echo "  Response: $BODY"
fi

echo ""

# Test 2: Missing file
echo "Test 2: Missing file parameter"
RESPONSE=$(curl -s -X POST http://localhost:8000/api/dice/calculate/ \
  -F "name=TestGroup" \
  -w "\n%{http_code}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "400" ]; then
    echo "✓ Status: 400 Bad Request"
    echo "  Response: $BODY"
else
    echo "✗ Expected 400, got: $HTTP_CODE"
fi

echo ""

# Test 3: Missing name
echo "Test 3: Missing name parameter"
RESPONSE=$(curl -s -X POST http://localhost:8000/api/dice/calculate/ \
  -F "file=@/tmp/test_submission.nii.gz" \
  -w "\n%{http_code}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "400" ]; then
    echo "✓ Status: 400 Bad Request"
    echo "  Response: $BODY"
else
    echo "✗ Expected 400, got: $HTTP_CODE"
fi

echo ""

# Check results file
echo "Checking results file..."
if [ -f "results/results.json" ]; then
    echo "✓ Results file exists"
    echo "  Content:"
    cat results/results.json | sed 's/^/  /'
else
    echo "✗ Results file not found"
fi

echo ""
echo "Stopping server..."
kill $SERVER_PID
wait $SERVER_PID 2>/dev/null
echo "✓ Server stopped"

echo ""
echo "================================"
echo "All tests completed!"
echo "================================"
