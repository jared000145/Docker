FROM node:24-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force && addgroup -S app && adduser -S -G app app
COPY --chown=app:app . .
USER app
EXPOSE 8888
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 CMD node -e "require('http').get('http://127.0.0.1:8888/health',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"
CMD ["npm", "start"]
