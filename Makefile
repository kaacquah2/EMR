.PHONY: demo

demo:
\tdocker compose up --build -d && \
\tdocker compose exec backend python manage.py migrate && \
\tdocker compose exec backend python manage.py setup_dev && \
\tdocker compose exec backend python manage.py load_demo_patients
