FROM kimbtechnologies/php_nginx:latest

ARG ALPINE_MIRROR=https://dl-cdn.alpinelinux.org/alpine

# php redis support
RUN sed -i \
		-e "s|https://dl-cdn.alpinelinux.org/alpine|${ALPINE_MIRROR}|g" \
		-e "s|http://dl-cdn.alpinelinux.org/alpine|${ALPINE_MIRROR}|g" \
		/etc/apk/repositories \
	&& apk add --update --no-cache $PHPIZE_DEPS \
	&& pecl install redis \
	&& docker-php-ext-enable redis

# SVG -> PNG convert
RUN apk add --update --no-cache rsvg-convert

# copy php files, nginx conf and startup scripts
COPY --chown=www-data:www-data ./php/ /php-code/
COPY ./utils/nginx.conf /etc/nginx/more-server-conf.conf 
COPY ./utils/startup.php /utils/startup-before.sh ./utils/cron.php  /

# backup default data dir
RUN mkdir /data-dir-default/ \
	&& cp -r /php-code/data/* /data-dir-default \
	&& mkdir /media-dir-default/ \
	&& cp -r /php-code/media/* /media-dir-default

ENV DOCKER_MODE=true
