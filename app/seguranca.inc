# Cabeçalhos de segurança, incluídos em cada location (add_header não é herdado se o
# location define outro add_header).
# Referrer-Policy NÃO pode ser "no-referrer": os mapas do OpenStreetMap exigem o Referer.
# Câmera e GPS só para o próprio site.
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(self), camera=(self), microphone=()" always;
add_header X-Frame-Options "DENY" always;
