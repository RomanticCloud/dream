#!/usr/bin/env python3
"""Minimal smoke test for the dream skill."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import json


SCRIPT_DIR = Path(__file__).resolve().parent


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_prompt_file_from_context(root: Path) -> Path:
    request_file = root / "context" / "latest_task_request.json"
    if request_file.exists():
        payload = json.loads(request_file.read_text(encoding="utf-8"))
        return Path(payload["prompt_file"])
    manifest_file = root / "context" / "latest_generation_manifest.json"
    if manifest_file.exists():
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
        return Path(payload["prompt_file"])
    prompt_file = root / "context" / "subagent_prompt.md"
    if prompt_file.exists():
        return prompt_file
    raise FileNotFoundError("未找到 latest_task_request.json、latest_generation_manifest.json 或 context/subagent_prompt.md")


def build_fixture(root: Path) -> None:
    write(root / "wizard_state.json", """{
  "basic_specs": {"chapter_length": "3500-4500字", "chapter_length_min": 3500, "chapter_length_max": 4500, "pacing": "偏快（每章推进）", "style_tone": "悬疑推理", "main_genres": ["悬疑推理"]},
  "protagonist": {"gender": "男"},
  "positioning": {"narrative_style": "第三人称有限视角", "main_conflicts": ["谜题揭晓", "危机追逐"], "reader_hooks": ["看真相浮出"], "core_promise": "主角在迷雾中逼近真相"},
  "world": {"setting_type": "现代都市", "society_structure": "平衡制衡", "main_scene": ["旧城区档案馆"]},
  "volume_architecture": {"volume_count": 2, "chapters_per_volume": 2},
  "batch_plan": {"first_volume_goal": "找到失踪档案", "first_volume_hook": "第二份证词出现"},
  "naming": {"selected_book_title": "档案馆迷案"}
}""")
    write(root / "reference" / "卷纲总表.md", """# 卷纲总表

## 第1卷 · 初始阶段
- 卷定位：故事开篇，建立谜案基础
- 卷目标：找到失踪档案
- 核心冲突：谜题揭晓、危机追逐
- 卷尾钩子：第二份证词出现
- 预估章数：2章

## 第2卷 · 阶段2
- 卷定位：故事推进，冲突升级
- 卷目标：追查证词来源
- 核心冲突：谜题揭晓、危机追逐
- 卷尾钩子：真正嫌疑人现身
- 预估章数：2章
""")
    write(root / "chapters" / "vol01" / "ch01.md", """# 第1章

## 正文

林舟走进旧城区档案馆时，天色已经压到傍晚，老楼外墙被雨水冲得发黑，门廊下的铁牌也锈得看不清原本的漆字。馆里照例没有多少访客，只有翻阅旧报纸时纸页摩擦的轻响，从阅览区一阵阵传过来。他抬手压低帽檐，先去总目录柜台核对火灾档案的编号。那场火灾发生在十二年前，案卷按理应放在封存区西侧第三列，可当他把目录抽出时，原本应该夹在中间的那一页却只剩下一道撕裂过的毛边。纸张纤维像被仓促扯断，细碎得像风干的鱼骨，和旁边保存完好的目录页形成刺眼反差。

林舟没有立刻惊动值班人员，而是站在柜台前把前后几页顺了一遍，确认缺失的不是随机一页，而是恰好能指向火灾卷宗存放位置的那一页。他把页码、编号和馆藏顺序在脑子里快速重组，推算出档案八成还在封存区，只是有人先一步动过手。这个判断让他心里那股隐约的不安慢慢收紧。若只是普通遗失，负责归档的人会留下空位说明，不可能只留下这样一段突兀的撕裂边。林舟顺手把旁边的检索登记簿翻开，指尖一页页滑过去，想找昨夜封存区的借阅记录，可登记簿最后一栏却在最关键的两小时出现了整段空白，像是有人故意避开了纸面痕迹。

他借着整理旧报纸的名义往封存区走去。档案馆的老式玻璃门推开时会发出沉闷的摩擦声，陈叔从柜台后抬头看了他一眼，目光停留片刻，却没有马上制止。林舟知道对方认得自己，也知道对方心里未必愿意他再查这件旧案，所以他没有多说，只是把一摞需要“核对年代”的报纸抱在怀里，动作自然地绕过阅览桌，来到封存区门前。那道门平日总锁着，今天却只是虚掩，像是离开的人走得太急，甚至没来得及把最后一步做完。林舟心里那点猜测立刻落了实。他用肩膀顶开门，鼻尖先闻到一股混杂着灰尘、潮气和旧纸发霉味道的冷气，像整间屋子都在提醒他，这里刚刚被人翻动过。

铁柜排列得很整齐，但灰尘不会骗人。第三列中段的一只柜门边缘，有一道新鲜的擦痕，在薄灰里划出明显的浅色轨迹。林舟弯下腰，顺着那道痕迹摸到柜底，又在门框旁发现两枚几乎要被忽略的泥点。昨夜下过雨，泥点边缘还带着未完全干透的细裂纹，说明来人不是馆里长住的人，而是从外面匆匆进来过。他把铁柜拉开，里面的案卷排列看似完整，真正的火灾档案却被抽走，留下一个勉强塞回去的旧文件袋。文件袋里只有几张不相关的废旧目录页，明显是有人想拖延后来者的判断时间。林舟把文件袋放到一边，又对着柜内剩余纸档的高低落差比了比，确认被抽走的不止一份，至少还有与火灾相关的关联材料一并消失了。

他正准备继续往深处搜，身后却传来陈叔压得很低的声音：“昨晚有人来过，不是馆里的人。”林舟回过头，看见老人站在门口，神情复杂得像压着一整段不愿提起的旧事。陈叔没有进来，只是停在灯光和阴影的交界处，低声说自己半夜听见封存区有动静，赶来时只看见一个背影，对方戴着雨帽，动作很熟，像对馆里的布局早有准备。林舟没追问太多，他知道对方既然愿意开口，就说明还留着一点合作的余地；若逼得太急，这点松动也会立刻关上。他只是让陈叔回忆来人停留在哪一列、是否带走了装档用的绳封、鞋底有没有泥。陈叔想了想，只说来人像是先翻登记，再进铁柜，临走前还在桌边停过几秒，像是在找什么能带走却又必须留下的东西。

这句话让林舟重新把注意力放回那本残缺目录上。他把刚才顺手塞进口袋的纸页拿出来，在门口昏黄灯光下一点点展开。页脚被水浸过，有一块墨迹已经晕开，但在最边缘的位置，仍能看见一道陌生签名。那不是完整的名字，更像是一段刻意压低笔锋后留下的代号，尾笔往上一挑，像一个故意递到他手里的暗示。林舟盯着那道签名看了很久，脑子里很快闪过火灾旧案里几个曾经出现过却始终没被证实的人物。他忽然意识到，对方抽走档案，不只是为了隐藏过去，更像是在逼某个人重新回到这条线索里。而那个人，或许就是自己。

封存区外的雨声渐渐变大，打在老旧玻璃上发出密集的噼啪声。林舟把签名小心夹进目录袋里，又把铁柜恢复成被翻动前的大致样子，免得惊动更多人。他没有带走任何原件，只在心里记下柜体编号、缺失位置和泥点分布。离开前，他最后看了一眼那扇半掩的门，忽然有种强烈的预感：昨夜来人并不怕有人发现档案被抽走，对方真正留下的，是这一道能把后续调查一点点牵引出去的标记。林舟收紧手里的目录袋，情绪由最初的谨慎慢慢转成一种近乎冷静的兴奋。他知道，自己终于摸到了这起旧案真正会咬人的地方，而那道陌生签名，就是今晚唯一值得死死抓住的线头。
""")
    write(root / "chapters" / "vol01" / "cards" / "ch01_card.md", """## 内部工作卡

### 1. 状态卡
- 主角当前位置：旧城区档案馆封存区
- 主角当前伤势/疲劳：无
- 主角当前情绪：警惕而兴奋
- 主角当前目标：确认失踪档案去向
- 本章结束后的状态变化：掌握第一条直指火灾档案的线索
- 本章时间流逝：2小时
- 本章结束时时间点：第1天傍晚

### 2. 情节卡
- 核心冲突：进入封存区寻找档案
- 关键事件：发现火灾档案被抽走并获得备用钥匙
- 转折点：页脚出现陌生签名
- 新埋伏笔：陌生签名与火灾档案的关系
- 回收伏笔：无

### 3. 资源卡
- 获得：+1值班钥匙
- 消耗：-1管理员信任额度
- 损失：无
- 需带到下章的状态：值班钥匙仍可使用
- 伏笔：陌生签名与火灾档案的关系

### 4. 关系卡
- 主要人物：林舟、陈叔
- 人物变化：林舟与陈叔形成有限合作

### 5. 情绪弧线卡
- 起始情绪：谨慎
- 变化过程：怀疑转为兴奋
- 目标情绪：坚定
- 悬念强度：7

### 6. 承上启下卡
- 下章必须接住什么：继续追查签名来源
- 下章不能忘什么限制：值班钥匙仍在手里
- 需要回收的伏笔：陌生签名与火灾档案的关系
- 新埋下的伏笔：档案馆深处还藏着第二份证词
- 本章留下的最强钩子是什么：铁柜深处可能还有第二份证词
""")
    write(root / "chapters" / "vol01" / "ch02.md", """# 第2章

## 正文

林舟没有让那道陌生签名在口袋里停太久。天刚黑透，他就把馆里的旧门禁记录、昨夜值班名单和火灾卷宗的残页重新摊开在地下整理室的木桌上。整理室的灯管老旧，亮起来时总会先轻轻闪一下，像有谁在暗处故意拖延时间。桌面上堆着半人高的旧档盒，空气里有种潮冷的霉味，和昨晚封存区里的味道几乎一模一样。林舟先从签名下手，把每一笔的收锋角度、停顿位置和用力习惯都拆开比对。他翻出馆内几份借阅申请，又调出许衡过去留下的几页存档说明，果然在两个毫不起眼的尾笔位置上看见了相同的抬锋习惯。这个发现没有让他松气，反而让心里的警惕更重。字迹能对上，不代表人就是真正动手的人，更多时候，能留下这种线索的人只是被推出来误导方向的中间层。

他顺着许衡这条线往下查时，先去找了陈叔。老人一夜没怎么合眼，神情比昨晚更疲惫，像终于意识到这件事不会在沉默里自动过去。林舟把目录残页和签名摊到对方面前，没有直接问“是不是许衡”，而是先问十二年前那场火灾后，馆里有没有谁被要求重新整理过纸档顺序。陈叔沉默了很久，手指无意识地在桌角一点点敲着，最后才承认，火灾后的第三天，确实有人连夜进馆重新封过一批档案。那时候许衡只是负责搬箱子的小职员，权限不足，不可能独自碰到最核心的案卷。但他替谁搬、替谁开过门，陈叔一直没说。直到此刻他才吐出一句含糊的补充：许衡那次之后突然换了住处，像是拿到一笔不该属于他的安家钱。

这句话让林舟意识到，许衡不是终点，只是能把调查继续往前拉的接口。他回到地下整理室，把许衡近几年留下的纸面记录全翻了一遍，从值班补签、领物登记到一次本该不起眼的设备报修单，全都逐条排开。他发现许衡有个习惯：每次在需要补签名字时，都会把最后一笔故意压低，像不愿让人一眼看清；可当他在某一份临时借阅条上写得太急时，这个压笔动作就会失控，露出完整的个人笔迹特征。林舟把那张借阅条和目录页脚一对，立刻确认签名确实出自许衡之手。但同时，记录里的时间差也暴露出另一个事实：许衡签下这道名字时，人并不一定在封存区里。他更像是在替某个真正掌握权限的人完成一层伪装，把调查者的视线暂时拽到自己身上。

为了验证这一点，林舟继续翻地下整理室里一排被长期忽视的旧转移箱。那些纸箱外侧都贴着早已泛黄的标签，记录着各类事故卷宗临时转移时的来源与去向。大多数人只会看标签，不会真把封条撬开去核内容，但林舟偏偏知道，真正有问题的东西往往藏在“看起来最规范”的箱子里。他拆开第三个箱子的外封时，里面掉出一张被折成四层的复印纸。纸面是一份火灾当夜的证词复印件，内容不完整，却足够关键。证词明确提到，在火灾发生前两个小时，曾有一批最敏感的纸档被提前转移，而执行转移的人并不是消防或调查组，而是一名持内部临时权限的人。这意味着火灾案从一开始就不是单纯的事故，而是有人先抽走关键材料，再借事故把整条证据链埋进废墟里。

林舟看完那张复印件时，几乎可以确定许衡只是替别人跑腿的人。他带着证词去找陈叔，老人看见复印件后脸色明显一沉，手背上的青筋都绷了起来。沉默了片刻后，陈叔终于承认，当年确实替人开过一次门。那晚来的人说是上面临时调卷，手续不全，却带着一个连馆长都不会轻易拿到的内部章。陈叔一开始不敢放人进去，可对方直接说出了封存区里那批火灾档的准确列号，像是早已提前踩过点。陈叔最终只开了第一道门，剩下的门是许衡陪着对方进去的。林舟追问对方长什么样，陈叔却摇头说当时光线太暗，只记得那人戴了帽子，手套一直没摘，走路很稳，不像第一次来馆里的人。

有了这层口供，林舟回头再看许衡留下的新地址，就看出那不是逃跑路线，而是故意交代给后来者的折返点。证词背面用极轻的笔压写着一串街巷号码，若不把纸斜着对光几乎看不出来。林舟把那串地址抄下来，与近年的租房登记一对，发现地址所在的并不是居民区，而是一片早该拆空的旧仓储地。那地方离档案馆并不远，却足够偏，适合临时存放不想放在明面上的东西。更重要的是，许衡最近几次夜间请假记录都指向同一个方向，说明他很可能被要求定期去那里交接某些纸面材料。到这里，许衡的角色已经非常清晰：他负责留下可被发现的痕迹，却没有资格掌握真正的核心内容。

为了继续追查签名来源，林舟把昨晚在封存区记下的每一处细节都重新摊开来比对。他没有把地下整理室当成一个突然切换的新场景，而是把它视作封存区调查的延长线：那里堆放的旧转移箱、封存时留下的编号、陈叔掌握的值班习惯，其实都和昨晚那只被翻动过的铁柜互相咬合。正因为他先在封存区发现了缺页和签名，今晚才知道该沿着哪一条线往下切到地下整理室。陈叔也终于明白，林舟不是在盲查，而是在顺着昨晚留下的唯一标记一点点逼近真正的取档人。两人从封存区回到地下整理室时，脚步都压得很轻，像怕把这条好不容易连起来的线索再次踩断。

林舟随后又把许衡这些年碰过的旧箱号按时间顺序重排，发现其中有三只箱子总会在火灾相关记录出现时被同时调动。第一只装的是失火楼层平面图，第二只装的是事发当夜值守名单，第三只则混着几份看似无关的设备保养表。单看任何一只箱子都像正常档务，连在一起却刚好能拼出一条能避开责任人的遮掩路线。林舟越看越确定，真正取档人之所以没把所有材料直接毁掉，是因为某些文件在未来还要继续被人使用，所以只能拆散、转移、埋进不同层级的旧档里，伪装成最不值得追查的日常纸面。这个判断让他对那串新地址的分量有了更清楚的认识：那里未必藏着全部真相，但一定藏着下一步能把中间人和幕后者重新连上的东西。

整理室里那盏忽明忽暗的灯管在头顶轻轻响着，陈叔站在架子旁沉默了很久，才又补了一句：当年许衡把人带进去后，出来时手里拎着的袋子比进去时更沉，而且袋口还渗过水。林舟立刻想到，这意味着那批被转走的材料里可能不只有纸档，还有曾经在火灾现场被带出来的附属记录，甚至可能包括一份从未进入正式卷宗的原始证据。他没有把这个猜测直接说透，只是把几处关键时间点记在掌心，又顺着陈叔描述的路线把地下整理室到封存区之间的门锁、转角和监控盲区全部重新走了一遍。等他停下来时，心里已经勾出一条大致路线：昨夜来人先在封存区找缺页位置，再到地下整理室确认替换材料，最后才借许衡留下的新地址，把所有怀疑都引向下一个折返点。

这条路线让本章的收束变得更明确了。许衡只是中间人，新地址只是门槛，真正值得追的，是那批被提前转移的火灾核心纸档，以及那个至今仍能调动馆内旧档结构的人。林舟把这些判断压回心底，重新整理好桌面，把几份被翻出来的材料一一归位，只留下自己真正需要带走的摘要和地址。走出地下整理室前，他最后一次回头确认门锁位置，心里已经把下一章要接住的事情排得清清楚楚：先去新地址，再找真正取档人，再把昨夜封存区和今晚整理室里留下的所有痕迹对成一条完整链。直到这时，他才真正感觉到，自己已经从“发现异常”走进了“能够反咬回去”的阶段。

事情推进到这一步，林舟心里反而没有预想中的轻松。真相离得更近，风险也更近。地下整理室外的脚步声时不时从走廊尽头掠过，像有人在确认这里的灯为什么还亮着。他把复印件重新夹回旧卷宗里，只留下一份手写摘要塞进口袋，以免原件突然失踪时自己什么都抓不住。陈叔站在桌边，看着那份证词，神情已经从回避变成某种迟来的恐惧。林舟没有再逼对方，他知道老人能说到这一步，已经是在拿多年沉默换眼下这点补偿。他只是低声说了一句，等今晚过去，自己会去那个新地址看看，但在那之前，任何人问起，都不要承认地下整理室里被翻出过第二份证词。

离开前，他又把所有登记表和证词复印件的顺序恢复原状，只在最不起眼的位置留了一个只有自己能认出的折角。新的追查方向已经被明确锁定：许衡不是终点，新地址也不是终点，真正的取档人还站在更深处等着。但至少现在，这条线终于不再只是一个模糊的怀疑，而是一条可以继续往下咬住的实线。林舟推开整理室的门，楼道冷风顺着台阶灌下来，他的情绪从整晚的压迫和急切慢慢沉到了近乎锋利的清醒。下一次去那个地址时，自己面对的可能就不是被删改过的纸页，而是直接伸手的人。
""")
    write(root / "chapters" / "vol01" / "cards" / "ch02_card.md", """## 内部工作卡

### 1. 状态卡
- 主角当前位置：档案馆地下整理室
- 主角当前伤势/疲劳：轻微疲劳
- 主角当前情绪：紧绷但清醒
- 主角当前目标：追查新地址与真正取档人
- 本章结束后的状态变化：锁定下一卷的调查方向
- 本章时间流逝：3小时
- 本章结束时时间点：第2天清晨

### 2. 情节卡
- 核心冲突：在时间压力下拿到第二份证词
- 关键事件：确认许衡身份并得到新地址
- 转折点：真正取档人并非许衡
- 新埋伏笔：新地址背后可能藏着真正的取档人
- 回收伏笔：无

### 3. 资源卡
- 获得：+1第二份证词复印件
- 消耗：-1陈叔的隐瞒空间
- 损失：无
- 需带到下章的状态：第二份证词复印件
- 伏笔：新地址背后可能藏着真正的取档人

### 4. 关系卡
- 主要人物：林舟、陈叔、许衡
- 人物变化：林舟确认陈叔可被有限信任

### 5. 情绪弧线卡
- 起始情绪：压迫
- 变化过程：逼近真相后的冷静
- 目标情绪：专注
- 悬念强度：8

### 6. 承上启下卡
- 下章必须接住什么：追查新地址与取档人
- 下章不能忘什么限制：陈叔只提供了有限信息
- 需要回收的伏笔：新地址背后可能藏着真正的取档人
- 新埋下的伏笔：第二卷从新地址切入真正嫌疑人
- 本章留下的最强钩子是什么：新地址可能指向真正嫌疑人
""")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dream_smoke_") as temp_dir:
        root = Path(temp_dir)
        build_fixture(root)

        compile_result = run([sys.executable, "-m", "py_compile", *[str(path) for path in SCRIPT_DIR.glob("*.py")]], root)
        if compile_result.returncode != 0:
            print(compile_result.stderr or compile_result.stdout)
            return 1

        enrich_result = run([sys.executable, str(SCRIPT_DIR / "volume_state_enricher.py"), str(root), "1"], root)
        if enrich_result.returncode != 0:
            print(enrich_result.stderr or enrich_result.stdout)
            return 1

        flow_result = run([sys.executable, str(SCRIPT_DIR / "writing_flow.py"), str(root)], root)
        if flow_result.returncode != 0:
            print(flow_result.stdout)
            print(flow_result.stderr)
            return 1
        if '"status": "draft_required"' not in flow_result.stdout or '"reason": "next_volume"' not in flow_result.stdout:
            print(flow_result.stdout)
            print(flow_result.stderr)
            return 1

        menu_result = run([sys.executable, str(SCRIPT_DIR / "strict_interactive_runner.py"), "action-menu", str(root)], root)
        if "查看卷沉淀" not in menu_result.stdout and "章节回改动作" not in menu_result.stdout:
            print(menu_result.stdout)
            return 1

        volume_check_result = run([sys.executable, str(SCRIPT_DIR / "volume_ending_checker.py"), str(root), "1"], root)
        if "卷收尾检查" not in volume_check_result.stdout:
            print(volume_check_result.stdout)
            print(volume_check_result.stderr)
            return 1

        report_path = root / "VOLUME_ENDING_REPORT.md"
        fix_plan_path = root / "FIX_PLAN.json"
        if not report_path.exists() or not fix_plan_path.exists():
            print(volume_check_result.stdout)
            return 1

        volume_memory_text = (root / "reference" / "卷沉淀" / "vol01_state.json").read_text(encoding="utf-8")
        if '"stable_facts"' not in volume_memory_text or '"unverified_claims"' not in volume_memory_text or '"conflicts"' not in volume_memory_text:
            print(volume_memory_text)
            return 1

        prompt_result = run([sys.executable, str(SCRIPT_DIR / "new_chapter.py"), str(root), "--prompt-only"], root)
        if prompt_result.returncode != 0:
            print(prompt_result.stderr or prompt_result.stdout)
            return 1

        prompt_file = load_prompt_file_from_context(root)
        prompt_text = prompt_file.read_text(encoding="utf-8")
        if "章节生成任务" not in prompt_text or "正文只写入：" not in prompt_text or "工作卡只写入：" not in prompt_text or "正文文件不得包含 `## 内部工作卡`" not in prompt_text:
            print(prompt_text)
            return 1

        menu_after_pass = run([sys.executable, str(SCRIPT_DIR / "strict_interactive_runner.py"), "action-menu", str(root)], root)
        if "查看卷沉淀" not in menu_after_pass.stdout and "章节回改动作" not in menu_after_pass.stdout and "卷回改动作" not in menu_after_pass.stdout:
            print(menu_after_pass.stdout)
            return 1

        scaffold_result = run([sys.executable, str(SCRIPT_DIR / "new_chapter.py"), str(root)], root)
        if scaffold_result.returncode != 0:
            print(scaffold_result.stdout)
            print(scaffold_result.stderr)
            return 1
        next_content = root / "chapters" / "vol02" / "ch01.md"
        next_cards = root / "chapters" / "vol02" / "cards" / "ch01_card.md"
        if not next_content.exists() or not next_cards.exists():
            print("未生成分离结构的章节脚手架")
            return 1
        if "## 内部工作卡" in next_content.read_text(encoding="utf-8"):
            print(next_content.read_text(encoding="utf-8"))
            return 1
        if not next_cards.read_text(encoding="utf-8").startswith("## 内部工作卡"):
            print(next_cards.read_text(encoding="utf-8"))
            return 1

        chapter_issue_result = run([sys.executable, str(SCRIPT_DIR / "chapter_validator.py"), str(root), "2", "1", "--threshold", "0.85", "--json"], root)
        if chapter_issue_result.returncode == 0:
            print(chapter_issue_result.stdout)
            return 1

        revision_after_issue = (root / "REVISION_STATE.json").read_text(encoding="utf-8")
        if 'pending_regenerate' not in revision_after_issue and 'pending_polish' not in revision_after_issue and 'pending_rewrite_card' not in revision_after_issue:
            print(revision_after_issue)
            return 1
        if '"tasks"' not in revision_after_issue or '"instruction"' not in revision_after_issue or '"fix_method"' not in revision_after_issue:
            print(revision_after_issue)
            return 1
        if '"volume"' not in revision_after_issue:
            print(revision_after_issue)
            return 1

        prompt_after_issue = run([sys.executable, str(SCRIPT_DIR / "new_chapter.py"), str(root), "2", "1", "--prompt-only"], root)
        if prompt_after_issue.returncode != 0:
            print(prompt_after_issue.stdout)
            print(prompt_after_issue.stderr)
            return 1
        prompt_after_issue_text = load_prompt_file_from_context(root).read_text(encoding="utf-8")
        if "本轮修正要求" not in prompt_after_issue_text or "本轮修正模式：" not in prompt_after_issue_text or "[error][" not in prompt_after_issue_text:
            print(prompt_after_issue_text)
            return 1
        if "保留约束：" not in prompt_after_issue_text or "目标=" not in prompt_after_issue_text or "阻塞=是" not in prompt_after_issue_text:
            print(prompt_after_issue_text)
            return 1

        router_after_issue = run([sys.executable, str(SCRIPT_DIR / "volume_revision_router.py"), str(root), "2", "1", "--single"], root)
        if "【自动执行目标】" not in router_after_issue.stdout or "full_chapter" not in router_after_issue.stdout:
            print(router_after_issue.stdout)
            print(router_after_issue.stderr)
            return 1

        menu_after_issue = run([sys.executable, str(SCRIPT_DIR / "strict_interactive_runner.py"), "action-menu", str(root)], root)
        if "整章重写" not in menu_after_issue.stdout and "AI润色" not in menu_after_issue.stdout:
            print(menu_after_issue.stdout)
            return 1

        print("dream smoke test passed")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
