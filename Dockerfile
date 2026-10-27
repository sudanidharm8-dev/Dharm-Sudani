# ─── Stage 1: Build dependencies ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install only what's needed — no dev tools in final image
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ─── Stage 2: Lean production image ──────────────────────────────────────────
FROM python:3.11-slim AS production

WORKDIR /app

# Copy installed packages from builder (keeps final image small)
COPY --from=builder /root/.local /root/.local

# Copy application source
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Run as non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

# Cloud Run expects the app to listen on PORT (default 8080)
ENV PORT=8080

EXPOSE 8080

# Use uvicorn with single worker (Cloud Run scales via instances, not threads)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
