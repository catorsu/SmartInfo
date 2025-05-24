# SmartInfo/docker/postgres/Dockerfile
# Stage 1: Builder
FROM postgres:16-alpine AS builder

# Install build dependencies for SCWS and zhparser
# automake, libtool, autoconf, m4 are for SCWS autogen steps when building from git
# libxml2-dev is for SCWS XML dictionary support
RUN set -ex \
    && apk --no-cache add \
       git \
       build-base \
       linux-headers \
       make \
       postgresql-dev \
       automake \
       libtool \
       autoconf \
       m4 \
       bash \
       libxml2-dev \
       clang \
       llvm

# Compile SCWS from source (version 1.2.3 from GitHub)
WORKDIR /opt/build
RUN set -ex \
    && git clone --branch 1.2.3 --single-branch --depth 1 https://github.com/hightman/scws.git \
    && cd scws \
    && touch README \
    && aclocal \
    && autoconf \
    && autoheader \
    && libtoolize --force \
    && automake --add-missing \
    && ./configure --prefix=/usr/local \
    && make \
    && make install

# Compile zhparser (master branch from GitHub)
WORKDIR /opt/build
RUN set -ex \
    && git clone --branch master --single-branch --depth 1 https://github.com/amutu/zhparser.git \
    && cd zhparser \
    && make PG_CONFIG=/usr/local/bin/pg_config SCWS_HOME=/usr/local \
    && make PG_CONFIG=/usr/local/bin/pg_config SCWS_HOME=/usr/local install

# Stage 2: Final image
FROM postgres:16-alpine

# Set language environment variable for UTF-8 support
ENV LANG zh_CN.UTF-8

# Install runtime dependencies for SCWS (if it was linked against libxml2)
RUN apk --no-cache add libxml2

# Copy compiled artifacts from builder stage
COPY --from=builder /usr/local/lib/postgresql/zhparser.so /usr/local/lib/postgresql/
COPY --from=builder /usr/local/lib/libscws.so* /usr/local/lib/
COPY --from=builder /usr/local/share/postgresql/extension/zhparser.control /usr/local/share/postgresql/extension/
COPY --from=builder /usr/local/share/postgresql/extension/zhparser--*.sql /usr/local/share/postgresql/extension/
COPY --from=builder /usr/local/share/postgresql/tsearch_data/dict.utf8.xdb /usr/local/share/postgresql/tsearch_data/
COPY --from=builder /usr/local/share/postgresql/tsearch_data/rules.utf8.ini /usr/local/share/postgresql/tsearch_data/
# Copy bitcode if it exists (might not if not compiled with Clang/LLVM for PG JIT)
COPY --from=builder /usr/local/lib/postgresql/bitcode/zhparser* /usr/local/lib/postgresql/bitcode/

# Set LD_LIBRARY_PATH so PostgreSQL can find libscws.so
ENV LD_LIBRARY_PATH=/usr/local/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

# The init-db.sql script (mounted via docker-compose) will handle
# CREATE EXTENSION zhparser; and other TEXT SEARCH CONFIGURATION.

WORKDIR /