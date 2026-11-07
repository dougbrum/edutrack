# EduTrack — Sistema Web de Gestão de Aprendizagem

Projeto desenvolvido como Trabalho de Conclusão de Curso II (TCC II) do Bacharelado em Engenharia de Software da UniCesumar.

**Autor:** Douglas Ferreira Brum  
**Ano:** 2026

## Sobre o projeto

O EduTrack é um protótipo de sistema web desenvolvido para apoiar a gestão de informações acadêmicas no Ensino Fundamental, centralizando funcionalidades relacionadas a usuários, turmas, notas, frequências, boletins, relatórios e comunicados.

## Tecnologias utilizadas

- Python e Flask — back-end e API REST
- SQLite — banco de dados relacional
- React — interface web
- JWT — autenticação
- bcrypt — hash de senhas
- HTML e CSS — estrutura e estilização

## Funcionalidades

- Autenticação por perfil de usuário
- Gerenciamento de usuários e turmas
- Matrícula de alunos
- Vinculação de professores e disciplinas
- Lançamento de notas por bimestre
- Registro de frequência
- Consulta a boletins e relatórios
- Publicação e leitura de comunicados
- Dashboard com indicadores acadêmicos

## Como executar

É necessário ter Python instalado e conexão com a internet para carregar as bibliotecas do front-end disponibilizadas por CDN.

No terminal, dentro da pasta do projeto, execute:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Depois, acesse:

http://127.0.0.1:5000

## Metodologia de desenvolvimento

O projeto foi desenvolvido de forma iterativa, sem a adoção formal de uma metodologia ágil específica. As funcionalidades foram implementadas progressivamente, com testes e ajustes ao longo do processo.

## Validação

O trabalho documenta 15 casos de testes funcionais manuais, além de uma avaliação de usabilidade com três participantes.

## Observações

O EduTrack é um protótipo acadêmico destinado à demonstração das funcionalidades implementadas. Não foi preparado para utilização em ambiente de produção sem adaptações adicionais de segurança, infraestrutura e testes.

## Instituição

Centro Universitário de Maringá — UniCesumar  
Bacharelado em Engenharia de Software  
Trabalho de Conclusão de Curso II — 2026