-- Optional MySQL-only demonstration records. Do not run this file in production.
-- Demo user accounts are intentionally created by `python -m app.seed`, where passwords are hashed.

INSERT INTO roles (code, display_name) VALUES
    ('USER', 'Usuário'),
    ('METEOROLOGIST', 'Meteorologista'),
    ('ADMIN', 'Administrador')
ON DUPLICATE KEY UPDATE display_name = CASE code
    WHEN 'USER' THEN 'Usuário'
    WHEN 'METEOROLOGIST' THEN 'Meteorologista'
    WHEN 'ADMIN' THEN 'Administrador'
END;

INSERT INTO forecasts (
    source_key, created_by, city, state, `condition`, temperature_c, minimum_c,
    maximum_c, humidity, wind_kmh, rain_probability, severity, description,
    polygon, source_name, issued_at, valid_until, created_at
) VALUES (
    'DEMO-MONGAGUA-CURRENT', NULL, 'Mongagua', 'SP', 'Parcialmente nublado',
    23, 18, 26, 68, 14, 73, 'HIGH',
    'Risco de tempestades e rajadas de vento nas proximas horas.',
    JSON_OBJECT('type', 'Polygon', 'coordinates', JSON_ARRAY(JSON_ARRAY(
        JSON_ARRAY(-49.8, -20.0), JSON_ARRAY(-43.0, -20.0),
        JSON_ARRAY(-43.0, -26.2), JSON_ARRAY(-49.8, -26.2),
        JSON_ARRAY(-49.8, -20.0)
    ))),
    'DEMONSTRACAO - dados sem monitoramento em tempo real',
    UTC_TIMESTAMP(), DATE_ADD(UTC_TIMESTAMP(), INTERVAL 7 DAY), UTC_TIMESTAMP()
) ON DUPLICATE KEY UPDATE
    issued_at = UTC_TIMESTAMP(),
    valid_until = DATE_ADD(UTC_TIMESTAMP(), INTERVAL 7 DAY);

INSERT IGNORE INTO weather_alerts (
    source_key, is_demo, created_by, title, message, event_type, severity, area_name,
    latitude, longitude, radius_km, polygon, recommendations, issued_at,
    valid_until, created_at
) VALUES
    (
        CONCAT('DEMO-ALERT-TEMPESTADE-', YEARWEEK(UTC_DATE(), 3)), TRUE, NULL, 'Tempestade severa',
        'Ventos fortes e raios frequentes. Ha risco de alagamento e queda de arvores.',
        'SEVERE_STORM', 'CRITICAL', 'Baixada Santista', -24.1008, -46.6200, 30,
        NULL, JSON_ARRAY('Procure abrigo imediatamente', 'Evite areas abertas e arvores',
        'Mantenha-se longe de janelas'), UTC_TIMESTAMP(),
        DATE_ADD(UTC_DATE(), INTERVAL (7 - WEEKDAY(UTC_DATE())) DAY), UTC_TIMESTAMP()
    ),
    (
        CONCAT('DEMO-ALERT-VENDAVAL-', YEARWEEK(UTC_DATE(), 3)), TRUE, NULL, 'Vendaval',
        'Rajadas fortes podem ocorrer nas proximas horas.', 'WINDSTORM', 'HIGH',
        'Litoral de Sao Paulo', -24.1008, -46.6200, 30, NULL,
        JSON_ARRAY('Evite areas abertas', 'Afaste-se de arvores e postes'),
        UTC_TIMESTAMP(), DATE_ADD(UTC_DATE(), INTERVAL (7 - WEEKDAY(UTC_DATE())) DAY), UTC_TIMESTAMP()
    ),
    (
        CONCAT('DEMO-ALERT-CHUVA-', YEARWEEK(UTC_DATE(), 3)), TRUE, NULL, 'Chuva intensa',
        'Pode haver chuva intensa e pontos de alagamento.', 'HEAVY_RAIN', 'MODERATE',
        'Litoral Sul', -24.1008, -46.6200, 30, NULL,
        JSON_ARRAY('Evite areas sujeitas a alagamentos',
        'Reduza a velocidade no transito', 'Acompanhe novos alertas'),
        UTC_TIMESTAMP(), DATE_ADD(UTC_DATE(), INTERVAL (7 - WEEKDAY(UTC_DATE())) DAY), UTC_TIMESTAMP()
    );

INSERT INTO educational_contents (
    source_key, author_id, title, body, media_url, reference_url, published_at
) VALUES
    (
        'DEMO-EDU-TEMPESTADE', NULL, 'Como agir durante uma tempestade severa',
        'Permaneça em local coberto, afaste-se de janelas e não procure abrigo sob árvores. Acompanhe os avisos da Defesa Civil.',
        NULL, 'https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil', UTC_TIMESTAMP()
    ),
    (
        'DEMO-EDU-ALAGAMENTO', NULL, 'Cuidados em áreas com alagamento',
        'Nunca atravesse uma via alagada a pé ou de veículo. Procure uma rota elevada e ligue 199 em caso de risco.',
        NULL, 'https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil', UTC_TIMESTAMP()
    ),
    (
        'DEMO-EDU-ALERTAS', NULL, 'Entenda os níveis de alerta',
        'Os níveis indicam a gravidade potencial. Consulte a área afetada e as recomendações antes de agir.',
        NULL, 'https://portal.inmet.gov.br/', UTC_TIMESTAMP()
    )
ON DUPLICATE KEY UPDATE title = VALUES(title), body = VALUES(body),
    reference_url = VALUES(reference_url);
