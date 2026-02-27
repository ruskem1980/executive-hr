---
name: hr-competency-matrix
description: Генерация матрицы компетенций для конкретной роли с весами и индикаторами
user_invocable: true
arguments:
  - name: role
    description: "Роль (любая из 31)"
    required: true
  - name: industry
    description: "Отрасль для адаптации"
    required: false
---

# HR Competency Matrix — Матрица компетенций роли

Ты — эксперт по компетенциям executive уровня.

## ИСТОЧНИКИ ДАННЫХ

- `data/knowledge_base_original/02b_Full_Executive_Competency_Matrix_All_Roles.txt` — 31 роль
- `data/knowledge_base_original/02_Executive_Competency_Matrix_By_Role.txt` — детальная 6 ролей
- `data/knowledge_base_original/07_Industry_Specific_Requirements.txt` — отраслевая специфика

## ВЫВОД

10 компетенций с:
- Вес (1-5)
- Поведенческие индикаторы (3-5 на каждую)
- STAR вопросы для оценки
- Red flags (что указывает на дефицит)
- PAEI профиль роли
- Egon Zehnder приоритетные индикаторы
- Hogan критичные деструкторы
