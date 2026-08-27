!include "LogicLib.nsh"
!include "nsDialogs.nsh"

!ifndef BUILD_UNINSTALLER
  ; 这些变量和页面只属于安装器；卸载器编译时不应注册它们。
  Var desktopShortcutCheckbox
  Var createDesktopShortcut

  !macro customPageAfterChangeDir
    Page custom DesktopShortcutPageCreate DesktopShortcutPageLeave
  !macroend

  Function DesktopShortcutPageCreate
    StrCpy $createDesktopShortcut "1"
    nsDialogs::Create 1018
    Pop $0
    ${NSD_CreateLabel} 0 0 100% 24u "快捷方式"
    Pop $0
    ${NSD_CreateCheckbox} 0 32u 100% 12u "在桌面创建知域引擎快捷方式"
    Pop $desktopShortcutCheckbox
    ${NSD_Check} $desktopShortcutCheckbox
    nsDialogs::Show
  FunctionEnd

  Function DesktopShortcutPageLeave
    ${NSD_GetState} $desktopShortcutCheckbox $0
    ${If} $0 == ${BST_UNCHECKED}
      StrCpy $createDesktopShortcut "0"
    ${EndIf}
  FunctionEnd

  !macro customInstall
    ${If} $createDesktopShortcut == "0"
      Delete "$newDesktopLink"
    ${EndIf}
  !macroend
!endif

!macro customUnInstall
  ${IfNot} ${Silent}
    MessageBox MB_YESNO|MB_ICONQUESTION "是否同时删除知域引擎保存的本机数据和 AI 服务配置？$\r$\n选择“否”可在以后重新安装时继续使用。" IDYES removeUserData
    Goto keepUserData
    removeUserData:
      RMDir /r "$APPDATA\知域引擎"
    keepUserData:
  ${EndIf}
!macroend
