"""报告复现附录的排版内容。实验本身不依赖此文件或 python-docx。"""
import json
from docx.shared import Pt
from docx.oxml.ns import qn


def add_appendix(doc, h, table, root):
    record = json.loads((root / '复现输出_附录核验' / '复现核对记录.json').read_text(encoding='utf-8'))
    if record['status'] != 'passed' or not all(x['passed'] for x in record['checks']):
        raise ValueError('复现核验尚未全部通过，不能生成通过记录。')

    def ap(text):
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.paragraph_format.line_spacing = 1.13
        paragraph.add_run(text).font.size = Pt(10)
        return paragraph

    def code(lines):
        for line in lines:
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(2)
            paragraph.paragraph_format.line_spacing = 1.05
            paragraph.paragraph_format.keep_with_next = line != lines[-1]
            run = paragraph.add_run(line)
            run.font.name = '宋体'
            run.font.size = Pt(9)
            run._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'), '宋体')

    def page(title, level=2):
        heading = h(title, level)
        heading.paragraph_format.page_break_before = True

    page('附录 实验复现说明', 1)
    ap('本附录复现第四至六节已经完成的小规模实验。输入和规则均写在脚本中，无外部AIS文件、辅助数据或随机抽样，不需要设置随机种子。目标是重新计算并核对表4-1至表6-3；复现这些数值不等于验证真实海区变化，也不包括尚未开展的真实AIS实验。')
    h('A1 环境和文件准备', 2)
    ap('安装Python即可，建议使用与本次同一主次版本Python 3.12。本次实际测试为Windows 11、Python '+record['python_version']+'。三个主实验、三个独立核验程序和统一入口都只用标准库，无需pip安装任何计算包，无需联网、数据库或优化器。其他Python版本尚未逐一测试。')
    ap('报告和以下文件保存在同一项目目录；保留.report_build子目录。三份已存主结果JSON（文件名见A3）可用于逐字段比对，但不是实验输入，缺少它们仍可重算阈值。不要只分享Word文件而遗漏脚本。')
    code([
        '海洋技术挖掘/',
        '  AIS实验_一键复现.py',
        '  AIS缺测阈值_小规模穷举.py',
        '  AIS时间分辨率_船时对照.py',
        '  AIS缺测模型_删减检查.py',
        '  .report_build/',
        '    verify_simulation.py',
        '    verify_time_resolution.py',
        '    verify_presence_audit.py',
    ])
    h('A2 推荐运行方式', 2)
    ap('在PowerShell中运行下列命令。项目路径按实际保存位置调整；python必须指向已安装的Python解释器。若该命令不可用，可以用python.exe的完整路径，并在PowerShell中用&调用。本次使用已安装解释器的完整路径；其路径、实际命令和版本均保存在复现核对记录.json。')
    code([
        "$project = 'C:\\Users\\Zhuansun Yuqing\\Desktop\\海洋技术挖掘'",
        'Set-Location -LiteralPath $project',
        'python --version',
        'python -X utf8 ".\\AIS实验_一键复现.py" --output-dir "复现输出_附录核验"',
    ])
    ap('统一入口会先复制六个实验/核验脚本到新目录，再依次执行；从新目录读取结果后进行交叉核对，避免误读旧结果。目录必须尚不存在。本次随报告保存的复现输出_附录核验已存在，读者再次运行时只需把输出目录改为复现输出_第二次等新名称。请勿使用-O或-OO，它们会关闭内置断言。')

    page('A3 分步命令与输出位置')
    ap('如需逐步观察计算，可在项目目录分别执行以下命令。前三个主脚本会覆盖其自身所在目录里的同名JSON；后两份独立核验JSON写在.report_build内。建议先用统一入口建立副本，再到副本目录执行这些分步命令。')
    code([
        'python -X utf8 ".\\AIS缺测阈值_小规模穷举.py"',
        'python -X utf8 ".\\AIS时间分辨率_船时对照.py"',
        'python -X utf8 ".\\AIS缺测模型_删减检查.py"',
        'python -X utf8 ".\\.report_build\\verify_simulation.py"',
        'python -X utf8 ".\\.report_build\\verify_time_resolution.py"',
        'python -X utf8 ".\\.report_build\\verify_presence_audit.py"',
    ])
    ap('三个主输出依次为R1、R2、R3。以下简称只用于阅读附录，实际文件名保持完整：')
    code([
        'R1 = AIS缺测阈值_模拟结果.json',
        'R2 = AIS时间分辨率_船时结果.json',
        'R3 = AIS缺测模型_检查结果.json',
    ])
    ap('统一入口另保存logs目录下六份控制台日志、复现核对记录.json，以及复制的六份脚本。verify_simulation.py原本只向控制台打印JSON，统一入口将它另存为.report_build/verify_simulation_results.json。其余两个独立结果文件为verify_time_resolution_results.json和verify_presence_audit_results.json，均在.report_build内。')
    h('A4 第四节表格对应关系', 2)
    table(['报告表格','R1中的字段或计算','预期结果'], [
        ['表4-1 观测计数','input_observed_by_time_WE\n按时间排列，每行[W,E]','[2,1]、[2,1]、\n[1,2]、[1,2]'],
        ['表4-2 阈值与计数','models内free、one_block、two_blocks\n的threshold、admissible_count、optimal_count','阈值4、6、4\n合法数3003、248、418\n最优数9、10、1'],
        ['表4-3 代表补量','models内free和one_block的\nrepresentative_missing_by_time\n补后逐片值=观测+补量','自由补(0,1)两片\n再补(1,0)两片\n单块前两片各补(0,3)'],
        ['表4-4 预算边界','上述三模型的lower_delta_by_budget\n依次读取索引3、4、5、6','预算4时最小Δ依次\n为0、1/15、0'],
    ], [3.7, 7.2, 5.5])
    ap('表4-2的单位是船舶—时间片整数计数，三项依次是自由、单块、双块模型。R1的enumerated_configurations应为3003。搜索总量截止6源于已验证反例，并非活动容量。JSON中的分数以字符串保存，例如"1/15"，可直接按有理数理解。')

    page('A5 第五和六节表格对应关系')
    h('表5-1 三尺度船时阈值', 3)
    ap('读取R2的results数组，按h_minutes识别60、30、15分钟三行，不依赖数组下标猜测尺度。每行models中依次读取free、full_bin_positive、outage_region的threshold_vessel_hours，均应为字符串"4"、"6"、"4"。required_bins_for_2h分别为2、4、8。')
    ap('三项依次是自由、每格正漏计模型A、允许零漏计的范围模型B；第三项不是表4-2的双块模型。A、B是对照假设标签，不是算法名称；代码字段full_bin_positive、outage_region保持不变。单位均为船时。正式主实验三个尺度共用同一六船账本；B和自由模型的底层单位固定0.25船时，A的单位为片长h。')
    ap('observed_months_vessel_hours按[W前,E前,W后,E后]排列，三行均为["4","2","2","4"]。models各项的aggregate_vectors_enumerated是期×区四个聚合补量的枚举数：A为210、1820、20475；自由与B每行均为20475。verified_event_witnesses保存反例积分，at_least_2h_same_endpoint_control保存至少2小时的对照。')
    h('表6-1 删减检查和条件下界', 3)
    ap('R3的old_cross_period_mask_4_cells包含A、B的删减证据及conditional_minimum_in_box，分别为1、0。first_failure保存A的失败例；B为null。跨尺度1、0来自cross_resolution_fixed_region_floor_vessel_hours。局部枚举通过不是B的全域证明，全域结论仍依赖正文给出的规则论证。')
    h('表6-2 三海区逐区明细', 3)
    ap('读取R3.new_growth_example。truth_each_period是每一期相同的两个小时真值；observed_early与observed_late分别是前后期观测，每行列序均为[L,C,R]。将两行同一列相加，得到逐区船时。实际漏计=真值−观测。')
    ap('A补量取models.A.optimal[0]，为[1,1,1,1,1,1]。表中B补量特意取actual_hidden_early=[0,0,1,0,0,1]，并检查它属于models.B.optimal；不要默认取B的第一个最优解。六维顺序为[L第1小时,C第1小时,R第1小时,L第2小时,C第2小时,R第2小时]，同一区两格相加。后期两规则补量均为0；补后=观测+补量。')
    table(['表6-2合计行','真值','观测','实际漏计','A补','A补后','B补','B补后'], [
        ['前期',10,8,2,6,14,2,10], ['后期',10,10,0,0,10,0,10],
    ], [3.1,1.9,1.9,1.9,1.9,1.9,1.9,1.9])
    h('表6-3 三海区阈值与最优解数', 3)
    ap('在同一个new_growth_example中，models.A.threshold=6、models.B.threshold=2；optimal数组长度分别为1、21；enumerated=924。中区条件强制下界来自R3.new_first_period_mask_6_cells的A、B项conditional_minimum_in_box，分别为2、0。目标是后期总量≤前期总量，允许持平或下降，不是必须相等。')

    page('A6 独立核验口径和本次复跑记录')
    ap('独立程序用于交叉检查，以下差异需要先对齐，不能把所有原始字段机械地逐项比较。')
    ap('第一，verify_simulation.py的exactly_one_block_min_duration_2排除全零配置，合法数247；主实验包含全零，合法数248。加回全零后计数一致，阈值6和最优解数10原样一致。统一入口同时核对这个差异。')
    ap('第二，verify_time_resolution.py独立构造逐船可见账本，身份可见区间与主脚本不同，但每格真值和观测聚合相同；其自由模型的底层单位随h变化，主脚本自由模型固定0.25船时。因此它是聚合阈值的独立交叉核验，不是同一逐船账本逐项重放。正式的同账本尺度比较以R2为准。')
    ap('第三，verify_presence_audit.py检查整格删去、总预算域；主脚本检查单位减量、局部盒域。删减次数不能直接对照，可对照三海区阈值、最优解及条件下界。独立文件中的internal_second_example为内部附加例7、3，不是正文表6-3的6、2。')
    h('本次按上述入口实际执行的结果', 3)
    ap('执行日期为'+record['started_at'][:10]+'；输出目录为复现输出_附录核验。使用Python '+record['python_version']+'，六个子程序退出码全部为0；统一入口共完成'+str(len(record['checks']))+'项核对，全部通过。三个主JSON均在新目录重新生成，并与报告原有结果进行解析后的逐字段比较，完全一致。')
    table(['核对项','本次实得','报告位置'], [
        ['原始计数 自由 单块 双块','4、6、4','表4-2'],
        ['60分钟 自由 A B 船时','4、6、4','表5-1 第一行'],
        ['30分钟 自由 A B 船时','4、6、4','表5-1 第二行'],
        ['15分钟 自由 A B 船时','4、6、4','表5-1 第三行'],
        ['三海区 A B 船时','6、2','表6-3'],
        ['三海区补后前期 A B 船时','14、10 后期均10','表6-2'],
    ], [7.1,4.7,4.6])
    ap('控制台最后应出现三行PASS，分别报告原始阈值、三尺度阈值、三海区阈值。复现核对记录.json的status应为passed，summary.all_checks_passed应为true，checks中每项passed应为true。记录同时保存实际命令、解释器路径、起止时间、脚本SHA-256和日志路径；若任何程序失败或数值不符，入口会报错并保存failed记录。')
    ap('实验复算不需要生成Word。若另行运行.report_build/build_report.py重建报告，才需要python-docx及报告构建文件，并保留本次复跑记录；排版导出与数值实验相互独立。这里只确认本报告列出的确定性算例可复现，不据此证明缺测假设合理或一般性方法优势。')
