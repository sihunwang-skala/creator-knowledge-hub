import { useEffect } from "react";

export type Language = "en" | "ko";

const KEY = "ckh-language";

export function getLanguage(): Language {
  try {
    return localStorage.getItem(KEY) === "en" ? "en" : "ko";
  } catch {
    return "ko";
  }
}

export function setLanguage(language: Language) {
  try { localStorage.setItem(KEY, language); } catch { /* ignore */ }
  location.reload();
}

const KO: Record<string, string> = {
  "Home Feed": "홈 피드",
  "My Creators": "내 크리에이터",
  "Quick Add": "빠른 추가",
  "Library": "라이브러리",
  "Topics & Collections": "주제 및 컬렉션",
  "Cross-Check": "교차 검증",
  "Weekly Digest": "주간 다이제스트",
  "Settings": "설정",
  "Menu": "메뉴",
  "Skip to content": "본문으로 건너뛰기",
  "Main": "주 메뉴",
  "Light mode": "라이트 모드",
  "Dark mode": "다크 모드",
  "Page not found.": "페이지를 찾을 수 없습니다.",
  "Follow creators you choose, keep your own notes, and search what you learned. Your library is private by default.": "원하는 크리에이터를 팔로우하고, 나만의 노트를 보관하며, 배운 내용을 검색하세요. 라이브러리는 기본적으로 비공개입니다.",
  "Your name": "이름",
  "Create local profile": "로컬 프로필 만들기",
  "A random access token is stored in this browser. No password, no tracking. Nothing is sent to an AI provider unless you opt in under Settings.": "임의 액세스 토큰이 이 브라우저에 저장됩니다. 비밀번호와 추적은 없으며, 설정에서 동의하지 않는 한 AI 제공업체로 아무것도 전송되지 않습니다.",
  "New uploads from creators you chose.": "선택한 크리에이터의 새 업로드입니다.",
  "Filter by creator": "크리에이터로 필터링",
  "All creators": "모든 크리에이터",
  "Checking…": "확인 중…",
  "Check for new videos": "새 동영상 확인",
  "Your feed is empty": "피드가 비어 있습니다",
  "No new videos yet. Use “Check for new videos”.": "아직 새 동영상이 없습니다. ‘새 동영상 확인’을 사용하세요.",
  "adding creators": "크리에이터 추가",
  "Add to library": "라이브러리에 추가",
  "Hide": "숨기기",
  "Demo data": "데모 데이터",
  "Has captions on YouTube": "YouTube 자막 있음",
  "Outside your topics": "관심 주제 외",
  "Channels you follow. Videos are discovered with the official YouTube Data API.": "팔로우 중인 채널입니다. 동영상은 공식 YouTube Data API로 검색됩니다.",
  "Channel URL, @handle, or channel ID": "채널 URL, @핸들 또는 채널 ID",
  "Follow": "팔로우",
  "Search channels": "채널 검색",
  "No channels found.": "채널을 찾지 못했습니다.",
  "You are not following anyone yet": "아직 팔로우 중인 크리에이터가 없습니다",
  "Add a channel above to start building your feed.": "위에서 채널을 추가해 피드를 만들어 보세요.",
  "Favorite": "즐겨찾기",
  "Auto-discover": "자동 검색",
  "Unfollow": "팔로우 해제",
  "Topics of interest (comma separated)": "관심 주제(쉼표로 구분)",
  "Paste a YouTube video link to add it to your library.": "YouTube 동영상 링크를 붙여넣어 라이브러리에 추가하세요.",
  "Video URL": "동영상 URL",
  "That does not look like a YouTube video link.": "올바른 YouTube 동영상 링크가 아닌 것 같습니다.",
  "Metadata and a bookmark are saved immediately. AI analysis only starts once you attach a source you have permission to use.": "메타데이터와 북마크는 즉시 저장됩니다. 사용 권한이 있는 출처를 첨부한 뒤에만 AI 분석이 시작됩니다.",
  "Adding…": "추가 중…",
  "Add video": "동영상 추가",
  "Open on YouTube": "YouTube에서 열기",
  "Hide player": "플레이어 숨기기",
  "Show player": "플레이어 보기",
  "Metadata unavailable": "메타데이터 없음",
  "Source required.": "출처가 필요합니다.",
  "This video is saved as a bookmark. We never summarise from the title or description, and we don’t fetch YouTube captions. Attach a transcript you’re allowed to use to enable AI notes.": "이 동영상은 북마크로 저장되었습니다. 제목이나 설명만으로 요약하지 않으며 YouTube 자막도 가져오지 않습니다. AI 노트를 사용하려면 사용 권한이 있는 스크립트를 첨부하세요.",
  "AI notes": "AI 노트",
  "Style": "스타일",
  "Analyzing…": "분석 중…",
  "Analyze with permitted source": "허용된 출처로 분석",
  "Analysis is disabled until at least one source is approved.": "하나 이상의 출처가 승인될 때까지 분석할 수 없습니다.",
  "Sources & permissions": "출처 및 권한",
  "No sources attached.": "첨부된 출처가 없습니다.",
  "Upload TXT/SRT/VTT": "TXT/SRT/VTT 업로드",
  "Write my own notes": "직접 노트 작성",
  "Licensed web page": "라이선스가 있는 웹페이지",
  "Source type": "출처 유형",
  "File (.txt, .srt, .vtt — max 1 MB)": "파일(.txt, .srt, .vtt — 최대 1MB)",
  "How did you obtain it?": "어떻게 확보했나요?",
  "My own / licensed file (private use)": "본인 소유/라이선스 파일(개인 사용)",
  "Provided by the creator": "크리에이터 제공",
  "Separately licensed transcript": "별도 라이선스 스크립트",
  "Podcast RSS transcript (licensed)": "팟캐스트 RSS 스크립트(라이선스 보유)",
  "Your notes about the video (analysed as your own writing)": "동영상에 대한 내 노트(본인 작성물로 분석)",
  "https URL of the licensed document": "라이선스 문서의 HTTPS URL",
  "License (e.g. CC-BY-4.0, “own content”)": "라이선스(예: CC-BY-4.0, ‘본인 콘텐츠’)",
  "Owner / creator": "소유자/크리에이터",
  "Source URL (optional, for citation)": "출처 URL(선택, 인용용)",
  "Permission evidence (link or description of your right to use this text)": "권한 증빙(이 텍스트를 사용할 권리에 관한 링크 또는 설명)",
  "Checking permission…": "권한 확인 중…",
  "Add source": "출처 추가",
  "Re-check": "다시 확인",
  "Delete source": "출처 삭제",
  "Permission evidence": "권한 증빙",
  "Add evidence of your right to use this text": "이 텍스트의 사용 권한 증빙 추가",
  "My Knowledge Library": "내 지식 라이브러리",
  "Everything you've saved, searchable.": "저장한 모든 내용을 검색할 수 있습니다.",
  "Export all (Markdown)": "전체 내보내기(Markdown)",
  "Search notes": "노트 검색",
  "Search notes…": "노트 검색…",
  "Favorites": "즐겨찾기",
  "No matching notes": "일치하는 노트가 없습니다",
  "Your library is empty": "라이브러리가 비어 있습니다",
  "Try a different search.": "다른 검색어를 사용해 보세요.",
  "Possible duplicate of": "중복 가능성:",
  "Export Markdown": "Markdown 내보내기",
  "Regenerate": "다시 생성",
  "Key points": "핵심 포인트",
  "Your edited version": "직접 편집한 버전",
  "Source": "출처",
  "AI-added": "AI 추가",
  "Action items": "실행 항목",
  "Glossary": "용어집",
  "Edit & annotate": "편집 및 주석",
  "Replace the AI text with your own version (Markdown)": "AI 텍스트를 직접 작성한 버전으로 교체(Markdown)",
  "Save my version": "내 버전 저장",
  "My notes": "내 노트",
  "Save notes": "노트 저장",
  "Claims & cross-check": "주장 및 교차 검증",
  "No checkable factual claims were found in this source.": "이 출처에서 검증 가능한 사실 주장을 찾지 못했습니다.",
  "Related notes": "관련 노트",
  "History": "기록",
  "Cross-check": "교차 검증",
  "Topics": "주제",
  "Tags appear here once you have notes.": "노트가 생성되면 태그가 여기에 표시됩니다.",
  "Collections": "컬렉션",
  "New collection name": "새 컬렉션 이름",
  "New collection": "새 컬렉션",
  "Create": "만들기",
  "Delete": "삭제",
  "Move a note into a collection": "노트를 컬렉션으로 이동",
  "Select…": "선택…",
  "Knowledge synthesis": "지식 종합",
  "No notes to combine yet": "아직 결합할 노트가 없습니다",
  "Topic title": "주제 제목",
  "Choose notes to merge": "병합할 노트 선택",
  "Download Markdown": "Markdown 다운로드",
  "Cross-Check Results": "교차 검증 결과",
  "Factual claims from your videos, compared with independent sources.": "동영상의 사실 주장을 독립적인 출처와 비교합니다.",
  "Filter by verdict": "판정으로 필터링",
  "All": "전체",
  "Copies of the same original count as one source. If nothing is found, a claim stays “Insufficient evidence” — never assumed true.": "동일 원본의 복사본은 하나의 출처로 계산합니다. 아무것도 찾지 못하면 주장은 ‘증거 불충분’으로 유지되며 사실로 간주하지 않습니다.",
  "No claims here": "주장이 없습니다",
  "open note": "노트 열기",
  "What’s new, what repeated, and what changed. Choose automatic delivery in Settings.": "새로운 내용, 반복된 내용, 변경된 내용을 확인하세요. 설정에서 자동 전달을 선택할 수 있습니다.",
  "Generate daily": "일간 생성",
  "Generate weekly": "주간 생성",
  "No digests yet": "아직 다이제스트가 없습니다",
  "Generate one to summarise recent activity.": "최근 활동을 요약하는 다이제스트를 생성하세요.",
  "Settings & Source Permissions": "설정 및 출처 권한",
  "Personalisation": "개인화",
  "Your role (shapes emphasis)": "역할(강조점에 반영)",
  "Interests (comma separated)": "관심사(쉼표로 구분)",
  "Default note style": "기본 노트 스타일",
  "Digest delivery": "다이제스트 전달",
  "Off": "끄기",
  "Daily": "매일",
  "Weekly": "매주",
  "Save": "저장",
  "Saved": "저장됨",
  "AI processing & privacy": "AI 처리 및 개인정보 보호",
  "Summariser:": "요약 도구:",
  "Local extractive (no data leaves this server)": "로컬 추출식(데이터가 서버 밖으로 나가지 않음)",
  "Source permission policy": "출처 권한 정책",
  "Allowed:": "허용됨:",
  "Prohibited (cannot be enabled):": "금지됨(활성화 불가):",
  "Disabled connectors:": "비활성 커넥터:",
  "Creator opt-in": "크리에이터 참여 신청",
  "Channel ID": "채널 ID",
  "Contact": "연락처",
  "Transcript license": "스크립트 라이선스",
  "Allow transcripts": "스크립트 허용",
  "Commercial use": "상업적 사용",
  "Register interest": "참여 의사 등록",
  "Delete my data": "내 데이터 삭제",
  "Delete everything": "모두 삭제",
  "Loading…": "불러오는 중…",
  "Permission required: ": "권한 필요: ",
  "Error: ": "오류: ",
  "Something went wrong": "문제가 발생했습니다",
  "Retry": "다시 시도",
  "Ready to analyze": "분석 준비됨",
  "Source required": "출처 필요",
  "Analysis unavailable": "분석 불가",
  "Processing": "처리 중",
  "Analyzed": "분석 완료",
  "Permission required": "권한 필요",
  "Unchecked": "미확인",
  "Supported": "근거 있음",
  "Partially supported": "부분적으로 근거 있음",
  "Contradicted": "반박됨",
  "Insufficient evidence": "증거 불충분",
  "Outdated": "오래된 정보",
  "never": "확인 안 됨",
  "just now": "방금 전",
};

function translateDynamic(text: string): string {
  const replacements: Array<[RegExp, string | ((...m: string[]) => string)]> = [
    [/^Demo mode: synthetic YouTube data \(no API key set\)\.$/, "데모 모드: 합성 YouTube 데이터(API 키 미설정)."],
    [/^Signed in as (.+)$/, (_m, name) => `${name}(으)로 로그인됨`],
    [/^Demo mode — try:$/, "데모 모드 — 예시:"],
    [/^checked (.+)$/, (_m, ago) => `${ago} 확인`],
    [/^Hide (.+)$/, (_m, title) => `${title} 숨기기`],
    [/^Unfollow (.+)\?$/, (_m, title) => `${title} 팔로우를 해제할까요?`],
    [/^Tag: (.+) ✕$/, (_m, tag) => `태그: ${tag} ✕`],
    [/^(\d+) min ago$/, (_m, n) => `${n}분 전`],
    [/^(\d+) h ago$/, (_m, n) => `${n}시간 전`],
    [/^(\d+) d ago$/, (_m, n) => `${n}일 전`],
    [/^Create synthesis \((\d+)\)$/, (_m, n) => `지식 종합 만들기 (${n})`],
    [/^(.+) digest — (.+)$/, (_m, freq, date) => `${freq === "daily" ? "일간" : "주간"} 다이제스트 — ${date}`],
  ];
  for (const [pattern, replacement] of replacements) {
    if (pattern.test(text)) return text.replace(pattern, replacement as string);
  }
  return text;
}

function translateNode(root: ParentNode) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  for (const node of nodes) {
    if (node.parentElement?.closest("script,style")) continue;
    const raw = node.data;
    const trimmed = raw.trim();
    if (!trimmed) continue;
    const translated = KO[trimmed] ?? translateDynamic(trimmed);
    if (translated !== trimmed) node.data = raw.replace(trimmed, translated);
  }
  const attrs = ["placeholder", "aria-label", "title"];
  for (const el of root.querySelectorAll<HTMLElement>("*")) {
    for (const attr of attrs) {
      const value = el.getAttribute(attr);
      if (!value) continue;
      const translated = KO[value] ?? translateDynamic(value);
      if (translated !== value) el.setAttribute(attr, translated);
    }
  }
}

/** Localises static UI copy, including content mounted after API requests finish. */
export function useUiTranslation(language: Language) {
  useEffect(() => {
    document.documentElement.lang = language;
    if (language !== "ko") return;
    let active = true;
    const scan = () => { if (active) translateNode(document.body); };
    scan();
    const observer = new MutationObserver(scan);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["placeholder", "aria-label", "title"] });
    return () => { active = false; observer.disconnect(); };
  }, [language]);
}
