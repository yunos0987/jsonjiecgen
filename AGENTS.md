
# 共通
- CLAUDE.md(AGENTS.md)とAGENTS.md(CLAUDE.md)を同期
- /testsディレクトリを作成
- /.vscodeディレクトリを作成
- /.vscode/launch.jsonファイルを作成し、/testsディレクトリ以下の単体テストを実行するタスク"unittest"を追加
- /tests/inputsのテストに変更がある場合、/tests/output/test_all.txtを見直すこと。

# IEC 61131-3コードルール
- 変数名は2文字以上とし、予約語を使用しない。
- POU呼び出しにおいて、仮引数有無の混在は不可。仮引数無しで統一するか、仮引数有りで統一する。特にenoを含む場合、必ず仮引数有りで統一する。
- 一行コメントは、// ~ を使用する。
- 複数行コメントは、(* ~ *) を使用する。
- コメントは、英語とする。
- 符号有無の混在する比較は不可。e.g. dintv > uintv is error.
- IEC 61131-3キーワードは、小文字とする。e.g. true, if.
- stringのサイズ属性は、NIL文字分を含めて指定する。

# Pythonコードルール
- コメントは、英語とする。

# Workflow
- リサーチ・調査は、サブエージェントに任せる。
