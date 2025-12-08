# TS-STATS-001: Project Statistics Report

## References
- Project structure in repository root
- Ignore patterns: `__pycache__`, `.pytest_cache`, `.git`, `simulations/`, `venv`, `.egg-info`, `*.pyc`

## Context
Нужно собрать статистику проекта для социального поста. Скрипт должен подсчитать количество файлов и строк кода/текста в разрезе категорий.

## Категории для подсчёта

### КОД (`src/`)
| Разрез | Путь |
|--------|------|
| Core | `src/*.py` |
| Phases | `src/phases/*.py` |
| Utils | `src/utils/*.py` + `src/utils/llm_adapters/*.py` |

### ТЕСТЫ (`tests/`)
| Разрез | Путь |
|--------|------|
| Unit | `tests/unit/*.py` |
| Integration | `tests/integration/*.py` |
| Shared | `tests/conftest.py` |

### ДОКУМЕНТАЦИЯ (`docs/`)
| Разрез | Путь |
|--------|------|
| Проектная | `docs/*.md` |
| Спеки | `docs/specs/*.md` |
| Задания | `docs/tasks/*.md` |

### ПРОМПТЫ (`src/prompts/`)
| Разрез | Путь |
|--------|------|
| Шаблоны | `src/prompts/*.md` |

## Метрики
Для каждого разреза:
- Количество файлов
- Количество строк

## Steps
1. Создать Python-скрипт для подсчёта статистики
2. Скрипт должен выводить результат в консоль в читаемом формате
3. Запустить скрипт и сохранить вывод

## Testing
```bash
source venv/bin/activate
ruff check <script>
ruff format <script>
mypy <script>
python <script>
```

## Deliverables
1. Скрипт статистики (можно временный, не коммитить)
2. Отчёт `TS-STATS-001_REPORT.md` с результатами подсчёта в табличном виде
