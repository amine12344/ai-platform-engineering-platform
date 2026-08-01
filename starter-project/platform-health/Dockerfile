ARG BASE_IMAGE=busybox:1.36.1
FROM ${BASE_IMAGE}

COPY www/ /www/

USER 65532:65532

EXPOSE 8080

ENTRYPOINT ["httpd", "-f", "-p", "8080", "-h", "/www"]