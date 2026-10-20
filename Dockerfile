# AWS Lambda container image serving the FieldLens HTTP API through Mangum.
FROM public.ecr.aws/lambda/python:3.12

COPY requirements-lambda.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements-lambda.txt

COPY fieldlens ${LAMBDA_TASK_ROOT}/fieldlens
COPY web ${LAMBDA_TASK_ROOT}/web
COPY samples ${LAMBDA_TASK_ROOT}/samples
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/lambda_handler.py
COPY lambda_http.py ${LAMBDA_TASK_ROOT}/lambda_http.py

CMD ["lambda_http.handler"]
