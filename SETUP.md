# VS Code에서 Jupyter Notebook 실행 환경 설정

## 필수 VS Code 확장

| 확장 | ID | 설명 |
|------|----|------|
| **Jupyter** | `ms-toolsai.jupyter` | 노트북 실행, 셀 편집, 출력 표시 |
| **Python** | `ms-python.python` | Python 인터프리터 감지, IntelliSense |

## Python 커널 선택

VS Code에서 `.ipynb` 파일을 열면 우측 상단에 "Select Kernel" 버튼이 보입니다.

### 문제: .venv가 커널 목록에 안 보이는 경우

VS Code는 **워크스페이스 루트**의 `.venv`만 자동 감지합니다. 하위 폴더(예: `movie-expert-agent/.venv`)에 있으면 목록에 나타나지 않습니다.

### 해결 방법

#### 방법 1: 인터프리터 경로 직접 입력 (권장)

1. 노트북 우측 상단 **"Select Kernel"** 클릭
2. **"Python Environments..."** 선택
3. **"Enter interpreter path..."** 선택
4. 경로 입력:
   ```
   ./movie-expert-agent/.venv/bin/python
   ```

#### 방법 2: 해당 프로젝트 폴더를 VS Code에서 직접 열기

```bash
code movie-expert-agent
```

이렇게 하면 VS Code가 `movie-expert-agent/.venv`를 자동으로 감지합니다.

#### 방법 3: VS Code 설정에 venv 경로 추가

`.vscode/settings.json`에 다음을 추가:

```json
{
  "python.venvFolders": [
    "movie-expert-agent"
  ]
}
```

## 셀 실행이 안 되는 경우 (Shift+Enter가 로딩만 되는 경우)

커널이 연결되지 않았거나 시작 중일 때 발생합니다.

1. **커널이 선택되었는지 확인** — 우측 상단에 Python 버전이 표시되어야 합니다
2. **커널 재시작** — `Cmd + Shift + P` → "Jupyter: Restart Kernel" 실행
3. **출력 초기화 후 재실행** — `Cmd + Shift + P` → "Notebook: Clear All Outputs" 후 다시 Shift+Enter
4. **ipykernel 설치 확인**:
   ```bash
   cd movie-expert-agent
   uv run python -m ipykernel --version
   ```
