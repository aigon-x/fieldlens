# AWS Lambda container image. The Lambda Python 3.12 base already provides the runtime
# interface client and boto3, so only the vision stack is installed: the web extras in
# requirements.txt (fastapi, uvicorn, multipart) are dead weight in the function package
# and lengthen the cold start.
FROM public.ecr.aws/lambda/python:3.12

# opencv-python-headless: no GUI/X11 libs needed in Lambda.
COPY requirements-lambda.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements-lambda.txt

COPY fieldlens ${LAMBDA_TASK_ROOT}/fieldlens
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/lambda_handler.py

CMD ["lambda_handler.handler"]
