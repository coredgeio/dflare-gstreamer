FROM node:20.9.0-alpine3.18 AS build-stage

RUN mkdir /src

WORKDIR /src 

COPY ./src .

RUN npm i -f

# Generate production build
RUN npm run build

FROM nginx:alpine

RUN \
    apk add -u --no-cache imagemagick bash

RUN mkdir /usr/share/nginx/html/app/

RUN mkdir /usr/share/nginx/html/app/lib

# Copy the dependencies and build from from build-stage
COPY --from=build-stage /src/app/lib /usr/share/nginx/html/app/lib 
COPY --from=build-stage /src/build/* /usr/share/nginx/html/
COPY --from=build-stage /src/app/lib/vue-v2.6.9.min.js /src/app/lib/vuetify-1.5.14.min.js  /usr/share/nginx/html/app/lib/
COPY --from=build-stage /src/app/sw.js /usr/share/nginx/html/app
COPY --from=build-stage /src/app/manifest.json /src/app/JioCloud_Icon_CMYK.png \
    src/app/start-workspace.svg src/app/top-left.svg  src/app/bottom-right.svg /src/app/favicon192.png  src/app/dflare-logo.png /usr/share/nginx/html/
# Implement cache busting patter for Caching the files
# COPY install.sh .
# RUN INSTALL_DIR="/usr/share/nginx/html" ./install.sh 

ENV GST_WEB_PORT=80
ENV PATH_PREFIX=/

CMD ["nginx", "-g", "daemon off;"]
