# Dockerfile
FROM php:8.2-fpm-alpine

# Install nginx + supervisor + common PHP deps
RUN apk add --no-cache nginx supervisor \
    mysql-client \
    && docker-php-ext-install opcache pdo pdo_mysql

# Create nginx runtime dirs
RUN mkdir -p /var/log/nginx /var/cache/nginx /var/run/nginx \
 && chown -R nginx:nginx /var/log/nginx /var/cache/nginx /var/run/nginx

# Nginx config
COPY docker/nginx/default.conf /etc/nginx/http.d/default.conf

# PHP upload / body limits + FPM timeout (persist across new containers)
COPY docker/php/uploads.ini /usr/local/etc/php/conf.d/uploads.ini
COPY docker/php/fpm-long-requests.conf /usr/local/etc/php-fpm.d/zz-long-requests.conf

# Copy ARC site into web root
COPY web/ /var/www/html/
RUN chown -R www-data:www-data /var/www/html

# Persist user datasets across redeploys by mounting volumes at:
#   /var/www/html/arc/home/data/uploads
#   /var/www/html/arc/home/data/artifacts
# (see docker-compose.yml)

# Init script (optional, but mirrors Flexus pattern)
COPY docker/init_pm.sh /usr/local/bin/init_pm.sh
RUN chmod +x /usr/local/bin/init_pm.sh

# Supervisord config
COPY docker/supervisord.conf /etc/supervisord.conf

EXPOSE 80
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
