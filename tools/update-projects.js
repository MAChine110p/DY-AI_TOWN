// 把工程登记进造世界编辑器的 projects.json（macOS 自带 JXA，无需安装 python）
// 用法：osascript -l JavaScript update-projects.js <projects目录> <工程文件夹名>
function run(argv) {
  ObjC.import('Foundation');

  const destDir = argv[0];
  const folder = argv[1];
  const jsonPath = destDir + '/projects.json';
  const projPath = destDir + '/' + folder;
  const fm = $.NSFileManager.defaultManager;

  let list = [];
  if (fm.fileExistsAtPath(jsonPath)) {
    const s = $.NSString.stringWithContentsOfFileEncodingError(jsonPath, $.NSUTF8StringEncoding, null);
    const txt = s.isNil() ? '' : s.js;
    if (txt.trim()) {
      try {
        const parsed = JSON.parse(txt);
        if (Array.isArray(parsed)) list = parsed;
      } catch (e) {
        console.log('⚠️ 原有 projects.json 解析失败，将新建一份');
      }
    }
  }

  // 优先沿用接收者自己的账号 uid，找不到才用原工程的
  let uid = '3309980302973310';
  for (let i = 0; i < list.length; i++) {
    if (list[i] && list[i].uid) { uid = String(list[i].uid); break; }
  }

  const now = Date.now();
  list = list.filter(function (e) { return !e || e.projectPath !== projPath; });
  list.push({
    projectPath: projPath,
    latestOpenTime: now,
    latestEditTime: now,
    uid: uid
  });

  const text = JSON.stringify(list, null, 2);
  const ok = $.NSString.stringWithString(text)
    .writeToFileAtomicallyEncodingError(jsonPath, true, $.NSUTF8StringEncoding, null);
  return ok ? 'ok' : 'failed';
}
