# Asteroids Game

Clone do clássico jogo Asteroids, feito em Python com Pygame. Naves, asteroides, tiros e detecção de colisão.

## Funcionalidades

- Movimentação e rotação da nave do jogador
- Sistema de tiro
- Geração contínua de campo de asteroides
- Detecção de colisão entre nave, tiros e asteroides
- Loop de jogo com limite de FPS

## Tecnologias

- Python 3.13+
- [Pygame](https://www.pygame.org/) 2.6.1
- [uv](https://docs.astral.sh/uv/) para gerenciamento de dependências

## Como rodar

```bash
uv sync
uv run main.py
```

Ou, sem `uv`:

```bash
pip install pygame==2.6.1
python main.py
```

## Estrutura do código

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Loop principal do jogo |
| `player.py` | Classe do jogador (movimento, rotação, tiro) |
| `asteroid.py` | Classe dos asteroides |
| `asteroidfield.py` | Geração e spawn contínuo de asteroides |
| `shot.py` | Classe dos projéteis |
| `circleshape.py` | Classe base com colisão circular, herdada por Player/Asteroid/Shot |
| `constants.py` | Constantes de configuração do jogo |
| `logger.py` | Logging de eventos e estado do jogo |
