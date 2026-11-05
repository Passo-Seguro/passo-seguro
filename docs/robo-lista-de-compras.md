# Robô inspetor: lista de compras

> **Rascunho.** Preços, lugares de compra e status são preenchidos pelo grupo.

## Microcontrolador

**A CONFIRMAR:** qual placa o kit do robô 2WD já traz.

- Se o robô usa **Arduino Uno**, será preciso comprar um **ESP32**, para ter Wi-Fi (enviar os relatos à API) e rodar o TinyML.
- Se o robô já tem **ESP32**, **não precisa comprar**.

Resultado da conferência:

- [ ] O kit tem Arduino Uno: comprar o ESP32.
- [ ] O kit já tem ESP32: não comprar.

## Itens

| Item | Quantidade | Obrigatório / condicional / opcional | Onde comprar | Preço | Status |
|---|---|---|---|---|---|
| MPU-6050 (acelerômetro e giroscópio) | 2 (1 + 1 reserva) | Obrigatório |  |  | Pendente |
| Sensor ultrassônico | 1 | Condicional: só se o robô não tiver |  |  | Aguardando conferência do kit |
| Buzzer ou módulo de voz | 1 | Obrigatório (confirmar) |  |  | Pendente |
| ESP32 | 1 | Condicional: só se o robô usar Arduino Uno (ver Microcontrolador) |  |  | Aguardando confirmação do microcontrolador |
| ESP32-CAM | 1 | Opcional |  |  | Pendente |
| Material da maquete (MDF ou papelão) |  | Obrigatório (confirmar) |  |  | Pendente |
| Suporte do sensor impresso em 3D | 1 | Obrigatório (confirmar) |  |  | Pendente |

Notas:

- A classificação "Obrigatório (confirmar)" do buzzer ou módulo de voz, da maquete e do suporte é uma sugestão inicial. Ajuste conforme o grupo decidir.
- A quantidade do material da maquete depende do tamanho do trecho; preencher depois de medir.
- Não inventar preços nem links: só registrar o que foi de fato consultado.
