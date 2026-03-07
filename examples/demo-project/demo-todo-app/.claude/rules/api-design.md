# API Design Rules

1. Use RESTful conventions (GET/POST/PUT/DELETE)
2. Return 404 for missing resources
3. Use Pydantic models for request/response schemas
4. Paginate list endpoints with `?page=1&size=20`
5. Use HTTP status codes correctly
