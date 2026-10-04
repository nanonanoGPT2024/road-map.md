#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stddef.h>

/* Struktur Data Zero-Copy String View */
typedef struct {
    const char *data;
    size_t len;
} str_view_t;

/* Struktur HTTP Request Line Tanpa Alokasi Heap */
typedef struct {
    str_view_t method;
    str_view_t uri;
    str_view_t path;
    str_view_t query_string;
    str_view_t version;
    bool has_query;
} http_request_line_t;

/* Kode Error Parsing */
typedef enum {
    PARSE_OK = 0,
    PARSE_ERR_EMPTY_BUFFER,
    PARSE_ERR_INVALID_METHOD,
    PARSE_ERR_INVALID_URI,
    PARSE_ERR_INVALID_VERSION,
    PARSE_ERR_MALFORMED
} parse_result_t;

/* Parser Zero-Copy */
parse_result_t parse_http_request_line(const char *buf, size_t buf_len, http_request_line_t *out_req) {
    if (!buf || buf_len == 0 || !out_req) {
        return PARSE_ERR_EMPTY_BUFFER;
    }

    const char *cursor = buf;
    const char *end = buf + buf_len;

    /* 1. Parse METHOD (Delimited by SPACE ' ') */
    const char *method_start = cursor;
    while (cursor < end && *cursor != ' ' && *cursor != '\r' && *cursor != '\n') {
        cursor++;
    }

    if (cursor >= end || *cursor != ' ') {
        return PARSE_ERR_INVALID_METHOD;
    }

    out_req->method.data = method_start;
    out_req->method.len = (size_t)(cursor - method_start);

    /* Lewati Spasi */
    cursor++;

    /* 2. Parse URI (Delimited by SPACE ' ') */
    const char *uri_start = cursor;
    while (cursor < end && *cursor != ' ' && *cursor != '\r' && *cursor != '\n') {
        cursor++;
    }

    if (cursor >= end || *cursor != ' ') {
        return PARSE_ERR_INVALID_URI;
    }

    out_req->uri.data = uri_start;
    out_req->uri.len = (size_t)(cursor - uri_start);

    /* Sub-parsing URI: Pisahkan Path dan Query String */
    const char *qmark = NULL;
    for (size_t i = 0; i < out_req->uri.len; ++i) {
        if (out_req->uri.data[i] == '?') {
            qmark = &out_req->uri.data[i];
            break;
        }
    }

    if (qmark) {
        out_req->path.data = out_req->uri.data;
        out_req->path.len = (size_t)(qmark - out_req->uri.data);
        out_req->query_string.data = qmark + 1;
        out_req->query_string.len = (size_t)(out_req->uri.data + out_req->uri.len - (qmark + 1));
        out_req->has_query = true;
    } else {
        out_req->path = out_req->uri;
        out_req->query_string.data = NULL;
        out_req->query_string.len = 0;
        out_req->has_query = false;
    }

    /* Lewati Spasi */
    cursor++;

    /* 3. Parse HTTP VERSION (Delimited by \r\n or \n) */
    const char *version_start = cursor;
    while (cursor < end && *cursor != '\r' && *cursor != '\n') {
        cursor++;
    }

    if (version_start == cursor) {
        return PARSE_ERR_INVALID_VERSION;
    }

    out_req->version.data = version_start;
    out_req->version.len = (size_t)(cursor - version_start);

    /* Validasi akhiran CRLF minimal */
    if (cursor < end && *cursor == '\r') {
        cursor++;
    }
    if (cursor >= end || *cursor != '\n') {
        return PARSE_ERR_MALFORMED;
    }

    return PARSE_OK;
}

/* Logging Observer Utility */
void print_http_request(const http_request_line_t *req) {
    printf("=== PARSED HTTP REQUEST (ZERO-COPY) ===\n");
    printf("Method       : %.*s\n", (int)req->method.len, req->method.data);
    printf("Full URI     : %.*s\n", (int)req->uri.len, req->uri.data);
    printf("Path         : %.*s\n", (int)req->path.len, req->path.data);
    if (req->has_query) {
        printf("Query String : %.*s\n", (int)req->query_string.len, req->query_string.data);
    } else {
        printf("Query String : (None)\n");
    }
    printf("Version      : %.*s\n", (int)req->version.len, req->version.data);
    printf("=======================================\n\n");
}

int main(void) {
    /* Simulasi Raw Buffer Paket Jaringan TCP yang Diterima Socket */
    char raw_network_buffer[] = 
        "POST /api/v2/telemetry/nodes?auth=token123&verbose=true HTTP/1.1\r\n"
        "Host: api.edge.internal\r\n"
        "Content-Type: application/json\r\n\r\n";

    size_t buffer_length = sizeof(raw_network_buffer) - 1; // Exclude \0 sistem

    http_request_line_t request;
    parse_result_t result = parse_http_request_line(raw_network_buffer, buffer_length, &request);

    if (result == PARSE_OK) {
        print_http_request(&request);
    } else {
        fprintf(stderr, "Parsing failed with error code: %d\n", result);
        return EXIT_FAILURE;
    }

    /* Validasi: Memverifikasi kesamaan tanpa modifikasi buffer */
    str_view_t expected_method = { .data = "POST", .len = 4 };
    if (request.method.len == expected_method.len &&
        memcmp(request.method.data, expected_method.data, 4) == 0) {
        printf("[ASSERTION PASSED] Method corresponds directly to source pointer.\n");
    }

    return EXIT_SUCCESS;
}
