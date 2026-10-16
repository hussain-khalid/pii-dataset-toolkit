# Leaderboard

Frozen benchmark id: `47c5878bf8034739`. Systems are ranked by F1; the interval is a 95% bootstrap over test records. Results from a different frozen id are not shown.

## Text PII detection

| Rank | System | Label set | Strict F1 (95% CI) | Relaxed F1 | Precision | Recall | False alarms on no-PII records |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | regex-rules | none | 0.805 (0.752 to 0.853) | 0.805 | 0.936 | 0.707 | 0.143 |
| 2 | empty | none | 0.000 (0.000 to 0.000) | 0.000 | 0.000 | 0.000 | 0.000 |

## Document field detection (box IoU of at least 0.5)

| Rank | System | Label set | F1 (95% CI) | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| 1 | ocr-regex | none | 0.667 (0.584 to 0.763) | 0.608 | 0.738 |
| 2 | empty | none | 0.000 (0.000 to 0.000) | 0.000 | 0.000 |

