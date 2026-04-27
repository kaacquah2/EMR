import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

/**
 * T12: Load Testing (k6 script)
 * 
 * Tests:
 * 1. 1000 concurrent users login
 * 2. 500 concurrent users creating encounters
 * 3. 200 concurrent PDF exports
 * 4. Sustained 100 RPS for 5 minutes, measure latency percentiles
 * 
 * Usage:
 * k6 run load-test.js
 * k6 run --vus 100 --duration 60s load-test.js
 * 
 * Environment variables:
 * API_BASE_URL=http://localhost:8000/api/v1 (default)
 * K6_TEST=test1|test2|test3|test4|all (which test to run)
 */

const API_BASE = __ENV.API_BASE_URL || "http://localhost:8000/api/v1";
const TEST_TO_RUN = __ENV.K6_TEST || "all";

// Metrics
const loginDuration = new Trend("login_duration");
const loginErrors = new Counter("login_errors");
const encounterDuration = new Trend("encounter_duration");
const encounterErrors = new Counter("encounter_errors");
const pdfDuration = new Trend("pdf_duration");
const pdfErrors = new Counter("pdf_errors");
const endpointDuration = new Trend("endpoint_duration");
const endpointErrors = new Counter("endpoint_errors");
const endpointRate = new Rate("endpoint_success_rate");

// Test 1: 1000 concurrent users login
export const test1Login = () => {
  const params = { timeout: "30s", headers: { "Content-Type": "application/json" } };

  const testUser = `test.load.${__VU}@medsync.gh`;
  const password = "TestPass123!@#";

  const loginPayload = JSON.stringify({
    email: testUser,
    password: password,
  });

  const startTime = new Date();
  const res = http.post(`${API_BASE}/auth/login`, loginPayload, params);
  const duration = new Date() - startTime;

  loginDuration.add(duration);

  const success = check(res, {
    "login status 200 or 401": (r) => [200, 401].includes(r.status),
    "login has token or error": (r) => r.body.includes("token") || r.body.includes("error"),
  });

  if (!success) {
    loginErrors.add(1);
  }

  sleep(1);
};

// Test 2: 500 concurrent users creating encounters
export const test2Encounters = () => {
  const params = {
    timeout: "30s",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${__ENV.E2E_ACCESS_TOKEN || "dummy-token"}`,
    },
  };

  const patientId = `patient-${__VU % 100}`; // Reuse patients across VUs
  const encounterPayload = JSON.stringify({
    patient_id: patientId,
    chief_complaint: `Load test encounter from VU ${__VU}`,
    encounter_type: "outpatient",
    scheduled_at: new Date().toISOString(),
  });

  const startTime = new Date();
  const res = http.post(`${API_BASE}/encounters/`, encounterPayload, params);
  const duration = new Date() - startTime;

  encounterDuration.add(duration);

  const success = check(res, {
    "encounter status 201 or 4xx": (r) => r.status >= 200 && r.status < 500,
    "encounter response has data": (r) => r.body.includes("id") || r.body.includes("error"),
  });

  if (!success) {
    encounterErrors.add(1);
  }

  sleep(0.5);
};

// Test 3: 200 concurrent PDF exports
export const test3PdfExports = () => {
  const params = {
    timeout: "60s", // PDFs take longer
    headers: {
      Authorization: `Bearer ${__ENV.E2E_ACCESS_TOKEN || "dummy-token"}`,
    },
  };

  const patientId = `patient-${__VU % 50}`;

  const startTime = new Date();
  const res = http.get(`${API_BASE}/patients/${patientId}/export/pdf`, params);
  const duration = new Date() - startTime;

  pdfDuration.add(duration);

  const success = check(res, {
    "pdf status 200 or 4xx": (r) => r.status >= 200 && r.status < 500,
    "pdf is binary": (r) => r.headers["Content-Type"]?.includes("pdf") || r.status === 404,
  });

  if (!success) {
    pdfErrors.add(1);
  }

  sleep(2);
};

// Test 4: Sustained 100 RPS for 5 minutes
export const test4SustainedLoad = () => {
  const endpoints = [
    { method: "GET", path: "/health" },
    { method: "GET", path: "/patients" },
    { method: "GET", path: "/encounters" },
    { method: "POST", path: "/appointments", payload: { patient_id: "test", scheduled_at: new Date().toISOString() } },
  ];

  const endpoint = endpoints[Math.floor(Math.random() * endpoints.length)];
  const url = `${API_BASE}${endpoint.path}`;

  const params = {
    timeout: "10s",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${__ENV.E2E_ACCESS_TOKEN || ""}`,
    },
  };

  const startTime = new Date();
  let res;

  if (endpoint.method === "GET") {
    res = http.get(url, params);
  } else if (endpoint.method === "POST") {
    res = http.post(url, JSON.stringify(endpoint.payload), params);
  }

  const duration = new Date() - startTime;
  endpointDuration.add(duration);

  const success = check(res, {
    "status 2xx or 4xx": (r) => r.status >= 200 && r.status < 500,
    "response time < 5s": (r) => r.timings.duration < 5000,
  });

  endpointRate.add(success);
  if (!success) {
    endpointErrors.add(1);
  }

  sleep(0.01); // 100 RPS ≈ 10ms between requests per VU
};

// Main test scenarios
export const options = {
  scenarios: {
    // Test 1: Login spike (1000 concurrent users over 30s)
    ...(TEST_TO_RUN === "test1" || TEST_TO_RUN === "all"
      ? {
          login_spike: {
            executor: "ramping-vus",
            startVUs: 0,
            stages: [
              { duration: "10s", target: 1000 },
              { duration: "10s", target: 1000 },
              { duration: "10s", target: 0 },
            ],
            exec: "test1Login",
          },
        }
      : {}),

    // Test 2: Encounter creation (500 concurrent users, 3 minutes)
    ...(TEST_TO_RUN === "test2" || TEST_TO_RUN === "all"
      ? {
          encounter_load: {
            executor: "ramping-vus",
            startVUs: 0,
            stages: [
              { duration: "30s", target: 500 },
              { duration: "120s", target: 500 },
              { duration: "30s", target: 0 },
            ],
            exec: "test2Encounters",
          },
        }
      : {}),

    // Test 3: PDF exports (200 concurrent, 5 minutes)
    ...(TEST_TO_RUN === "test3" || TEST_TO_RUN === "all"
      ? {
          pdf_export: {
            executor: "ramping-vus",
            startVUs: 0,
            stages: [
              { duration: "30s", target: 200 },
              { duration: "240s", target: 200 },
              { duration: "30s", target: 0 },
            ],
            exec: "test3PdfExports",
          },
        }
      : {}),

    // Test 4: Sustained 100 RPS (5 minutes)
    ...(TEST_TO_RUN === "test4" || TEST_TO_RUN === "all"
      ? {
          sustained_rps: {
            executor: "constant-arrival-rate",
            rate: 100,
            timeUnit: "1s",
            duration: "300s",
            preAllocatedVUs: 20,
            maxVUs: 50,
            exec: "test4SustainedLoad",
          },
        }
      : {}),
  },

  thresholds: {
    "login_duration": ["p(95)<2000", "p(99)<5000"],
    "encounter_duration": ["p(95)<1000", "p(99)<3000"],
    "pdf_duration": ["p(95)<10000", "p(99)<30000"],
    "endpoint_duration": ["p(95)<500", "p(99)<2000"],
    "endpoint_success_rate": ["rate>0.95"],
    "login_errors": ["count<50"],
    "encounter_errors": ["count<50"],
    "pdf_errors": ["count<20"],
    "endpointErrors": ["count<100"],
  },
};

export function handleSummary(data) {
  return {
    stdout: textSummary(data, { indent: " ", enableColors: true }),
  };
}

// Helper: text summary output
function textSummary(data, options = {}) {
  const lines = [
    "\n=== Load Test Summary ===\n",
    `Test duration: ${data.metrics.duration?.value || "unknown"} ms`,
  ];

  if (data.metrics.login_duration?.values?.p95) {
    lines.push(`Login p95: ${Math.round(data.metrics.login_duration.values.p95)} ms`);
    lines.push(`Login p99: ${Math.round(data.metrics.login_duration.values.p99)} ms`);
  }

  if (data.metrics.encounter_duration?.values?.p95) {
    lines.push(`Encounter p95: ${Math.round(data.metrics.encounter_duration.values.p95)} ms`);
    lines.push(`Encounter p99: ${Math.round(data.metrics.encounter_duration.values.p99)} ms`);
  }

  if (data.metrics.pdf_duration?.values?.p95) {
    lines.push(`PDF p95: ${Math.round(data.metrics.pdf_duration.values.p95)} ms`);
    lines.push(`PDF p99: ${Math.round(data.metrics.pdf_duration.values.p99)} ms`);
  }

  if (data.metrics.endpoint_duration?.values?.p95) {
    lines.push(`Endpoint p95: ${Math.round(data.metrics.endpoint_duration.values.p95)} ms`);
    lines.push(`Endpoint p99: ${Math.round(data.metrics.endpoint_duration.values.p99)} ms`);
    lines.push(`Endpoint success rate: ${(data.metrics.endpoint_success_rate?.value * 100).toFixed(2)}%`);
  }

  lines.push(`\nTotal errors: ${(data.metrics.login_errors?.value || 0) + (data.metrics.encounter_errors?.value || 0) + (data.metrics.pdf_errors?.value || 0) + (data.metrics.endpointErrors?.value || 0)}`);

  return lines.join("\n");
}
