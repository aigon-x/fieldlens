# AWS Lambda container image (not built in this session; build on the builder node).
# Lambda Python 3.12 base already provides the Lambda runtime interface client.
FROM public.ecr.aws/lambda/python:3.12

# opencv-python-headless: no GUI/X11 libs needed in Lambda.
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY fieldlens ${LAMBDA_TASK_ROOT}/fieldlens
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/lambda_handler.py

CMD ["lambda_handler.handler"]
