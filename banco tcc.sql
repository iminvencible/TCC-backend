create database if not exists PrevClima;

use PrevClima;

CREATE TABLE funcoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    funcao_id INT DEFAULT 2, -- Padrão: Comum
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (funcao_id) REFERENCES funcoes(id) -- Garante o vínculo seguro
);

CREATE TABLE alertas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT,
    titulo VARCHAR(100) NOT NULL,
    mensagem TEXT NOT NULL,
    tipo ENUM('info', 'aviso', 'erro', 'sucesso') DEFAULT 'info',
    lido BOOLEAN DEFAULT FALSE,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);


ALTER TABLE usuarios 
ADD COLUMN cidade VARCHAR(100),
ADD COLUMN estado VARCHAR(2);



INSERT INTO funcoes (nome) VALUES ('Administrador'), ('Comum'), ('meteorologista');


select * from usuarios;
select * from funcoes;
select * from alertas;