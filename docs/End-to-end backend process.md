## 后端流程

| 能力       | 验证方式                           |
| ---------- | ---------------------------------- |
| 注册，登录 | 新用户注册，老用户登录，密码编码   |
| 占卜       | 占卜流程出结果                     |
| 多轮问答   | 结合前轮解读，生成解答             |
| 数据保存   | 完成占卜，MySQL保存记录            |
| 访问       | 局域网内电脑能直接使用             |
| 权限       | 数据库单独管理，其他机器无删改权限 |



### 目标：建立占卜助手（包含八字，塔罗，六爻，星座，紫薇，黄历六种占卜方法）

（解释内容）：（）内为解释内容或流程判断

对话流功能：用户给出输入，系统判断用户想法，生成占卜方式，检索对应知识，生成解读，录入数据库，在用户追问时保持上下文不丢失

对话流框架：用户输入提取-->用户意图判断-->知识检索，模型解答-->生成回复，保存信息

框架底层架构：

- 用户输入提取：用户输入-->提取关键字-->输出加固判断（先验后加）-->判断数据（先验后加） 单独的提取用户输入的关键字进行识别，只能粗略的拿到用户想要占卜的方向（用大模型识别在第二轮追问问答中有高概率识别不到用户的占卜方向，且容易出现误判，用户可能在输入中不包含占卜方向，故用代码节点提取占卜方向的变量存储给对话流记忆），无法识别用户想用的占卜方式（用户不一定告诉你），因而需要补充‘输出加固判断’，同时记忆用户选择的占卜方式，‘输出加固判断’提取出用户的意图，故需要加一个判断，向后续节点输出
- 用户意图判断：问题分类-->参数提取（如有必要）-->代码生成占卜流程-->变量赋值 得到用户占卜方向及占卜方式之后，进入问题分类，分流进入到不同节点（八字，塔罗，六爻，星座，黄历，紫薇，根据上一轮内容追问，没有识别出具体方向和方法-->引导回答），根据实际情况发现八字，星座，紫薇三类方式需要知道用户信息，从而设置参数提取器，提取出必要内容给后一节点，进入代码生成占卜流程（略，见下文），后将代码节点输出变量进行赋值，主要包括占卜方式，占卜方向，历史信息等
- 知识检索，模型解答：判断卦-->知识检索-->解读-->变量聚合 判断节点通过用什么占卜方式决定后一节点的对应知识库，检索后用LLM解读，做变量聚合输出
- 生成回复，保存信息：格式转换-->拉取历史记录-->变量赋值-历史-->直接回复 对变量聚合的输出做统一，以免出现输出格式问题，由于极有可能出现二次对话，在输出之前建立拉取历史记录，存储历史记录于对话流变量，然后对变量进行赋值，最后端口接通，将内容放进数据库存储，以便用户调用，最后输出
- 为什么使用对话流：工作流为一次性输出，第二次输入不记得第一次对话，不适合做对话；Agent有自主性过高，之前用Coze做Agent带对话流和工作流，效果一般，容易与对话流打架，如果只带工作流，确定性不高

### 一些问题

问题分类器只看当前一句话，用户输入不完整，缺少方向或者方式，难以进入后续分析，会定义为其他类，一直让用户输出

解决办法：在问题分类器前加入输出加固判断，用代码强制控制节点，对于当前用户输入，如果识别出新方法，交给分类器处理；如果有对应方法路径，缺少参数，交给用户输入参数，如果有上下文，进入追问，都没有，交给分类器选择

代码节点产生占卜方式生成时，一轮对话没有问题，多轮对话会导致用户初始占卜方向丢失，导致对话失效，没有连贯性，各说各话

解决办法：设置话题方向变量，在进入代码生成占卜方式之前进行变量赋值，产生记忆，本轮数据正常流通，上轮数据存在变量，一直循环

代码生成占卜方式，产生的结果都是随机的（比如塔罗，六爻），要在多轮对话中保证结果跟第一轮一样

解决办法：在代码节点单独命制变量，记忆随机生成牌面，然后存入上下文变量，第二轮的输出如果与上下文不符合则输出上下文记忆内容

### 变量固定操作

1. 代码节点生成占卜流程后，产生的解读和追问问题等全部追加写入history和board，保证数据完整，如果利用LLM会导致数据可能丢失
2. 在八字，紫薇等这种需要用户信息的流程中，在参数全部齐全之后，pending清空，保证在后续用户输入后不会被再次要求补齐需要的信息
3. history做截断处理，只保留5条内容，防止内容过多时上下文拉爆，当然这里可以慢慢测试稳定性，适当调高阈值，或者降低，这取决于LLM

### 占卜边界

八字：不包含真太阳时，节气计算，换算太过复杂，使用LLM也容易出错，如果要改进可以用完整数据库查表之类的办法，联网搜索不可靠,耗时太久

紫薇：没有辅星，神煞，原因同上

星座：没有月亮和上升星座，原因同上

### MySQL处理

Dify插件只能读取MySQL内容，没有办法写入与修改，只能通过端口请求连接，Dify直连数据库会导致账号密码经过后台记录，既不安全，也没办法输出，只能通过前后端和数据库，Dify分开请求才能较好完成，前端页面在调用Dify时只生成解答，账号密码通过python后端记录编码，经过前端把占卜流程走完，传输给后端后，再一起打包给MySQL

### bug排查

1. 追问当成闲聊，在多轮对话中，系统没有记忆上下文整体，每次当成一次新开始，导致问题分类在多轮对话中，每一次都需要用户输入方向方式；
   通过问题分类节点之前，加入输出的判断，读取board，判断上下文，如果有，就走追问，如果没有，就由问题分类判断，我们也可以把上下文丢到用户输入里面一起给问题分类，但是有可能导致分类器紊乱，因为用户可能第一轮在用塔罗，第二轮想用八字，或者根本没有指定方式，LLM只负责理解，代码只负责规定
2. 用户在补充信息的时候，系统不知道是八字，紫薇还是星座当中的哪一个，容易将信息默认填充给八字分支；
   引入pending变量，记录用户选择的方式，通过pending来确定分支往哪里走，如果要调整方法，那么topic发生变化，pending清空即可，参数齐全进入后续流程，pending清空，保证对话流稳定，我们也可以使用LLM自动去识别用户的回答，但是用户键入的日期多种多样，而且还用公历农历等区分，LLM可能会理解错误，再要求绝对精确的条件下，我们还是使用代码
3. 塔罗测试发现topic为空
   topic被赋值在代码运行节点之后，导致LLM识别topic为空，没有提取到，在用户输入后就做一次topic定义读取即可，不让LLM读取旧topic，我们也可以把topic赋值放在代码运行之前，但是有多条分支，容易混乱，所以一轮的topic在对应方式里走，记忆之后，新一轮的topic在最开始直接定义
4. 数据库只读不写
   插件市场没工具，Dify没MySQL节点，只能自己写服务，提供端口
5. 数据写入，但是库不对
   本地直接连MySQL，可以正常写入，但是将MySQL挂在其他机器，导致数据写入，库中查不到，在多个MySQL存在的时候，用户名密码一样系统是不会区分的，只会走默认，我们只能把ip地址改成对应机器的ip，然后新建专门的账号
6. 前端接不上
   前后端的需求路径必须相同，返回字段必须一样，不然会导致数据无法返回，接口报错不存在
7. 局域网开页面崩盘
   主要是浏览器安全模式问题，远程要用https调用才是安全，用http会报不安全，导致打不开，前端写死了远程地址必须https，那么握手握不上，就没办法连接，因为后端是http，为什么不用https，因为内网ip没有办法签署证书，如果信任机器要手动信任所有机器，而且浏览器规范也会拒绝不受信证书，测试可以直接改校验，至于为什么，我搞不太懂

#### 能用代码用代码，用不了代码再给LLM，能用变量读取提示就用变量，用不了再用LLM

| 变量       | 类型   | 作用                            | 写入       | 读取       |
| ---------- | ------ | ------------------------------- | ---------- | ---------- |
| method     | string | 记录占卜方式                    | 变量赋值   | 解读，判断 |
| topic      | string | 记录用户占卜方向                | 提取关键字 | 解读       |
| board      | string | 代码节点上下文JSON格式，给程序  | 变量赋值   | 判断       |
| board_text | string | 代码节点上下文string格式，给LLM | 变量赋值   | 解读       |
| history    | string | 记录多轮对话                    | 变量赋值   | 解读       |
| pending    | number | 记录需要的参数                  | 判断分支   | 判断分支   |

###### 补充：

第一轮：开始-->代码运行（topic为空）-->变量赋值（写入topic == xxx）-->结束

第二轮：开始-->代码运行（topic == 第一轮xxx）-->变量赋值（新topic）-->结束

### 数据库与前端

流程：浏览器-->HTTP-->后端-->数据库

对应大概就是从浏览器开始，负责显示界面，发送请求和显示结果-->HTTP来解析路径和JSON，确定状态-->后端提供校验，令牌……-->数据库连接上后建表键值，执行sql

对于登录流程而言，浏览器通过端口访问HTTP，然后HTTP处理JSON取出路径传给后端python，py再查询（select …… from …… where ……），MySQL接收到之后就返回对应的字段给py，在这个过程中py会进行密码的编译，之后py得到返回的字段再给HTTP，这个返回的字段是py与前端对应的字段，HTTP得到字段后再把这部分给浏览器

#### 数据库层

主要写了个py文件

```python
DB_HOST = os.getenv("XINGXUN_DB_HOST", "127.0.0.1")        # 数据库所在机器的 IP
DB_PORT = int(os.getenv("XINGXUN_DB_PORT", "3306"))      # MySQL 默认端口
DB_USER = os.getenv("XINGXUN_DB_USER", "root")           # 专用账号，不是 root
DB_PASSWORD = os.getenv("XINGXUN_DB_PASSWORD", "")       # 从环境变量读，不写死
DB_NAME = os.getenv("XINGXUN_DB_NAME", "divination_simple")  # 库名
```

为什么用专门账号，前面解释过了，默认root，他识别不出来进哪个库，会宕机

```python
def get_conn():
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4"                   #整个不像之前，他非要加
    )
    return conn
```

这个charset要加是因为power shell这种只用gbk，不用utf8，所以必须加，然后返回值之前我们都是建立cursor返回，这里直接返回conn，是因为cursor是conn建立的，之前我们是一台机器测试，只需要跑一条，这个开多机器，他可能一次跑几条，所以不返回cursor，直接返回conn,让他自己来开

```python
conn = pymysql.connect(..., charset="utf8mb4")   # 没指定 database
cur = conn.cursor()

cur.execute("CREATE DATABASE IF NOT EXISTS %s DEFAULT CHARSET utf8mb4" % DB_NAME)
cur.execute("USE %s" % DB_NAME)

cur.execute("SHOW TABLES LIKE 'users'")
if cur.fetchone() is None:
    cur.execute("CREATE TABLE users (...)")
...
conn.commit()
```

这里conn没有指定库，是怕链接的时候还没库，所以先连接，然后再use database切过去，后面execute有%拼接，这里我查了一下，拼常量无所谓

建表的话有三张，users，history，divinations，users存储账号密码，history存储问题，方法等LLM的输出，divinations记录对应的JSON格式，这个比较重要，直接给系统转换，经常会出现乱码

```python
def get_user_id(cur, username):
    cur.execute("SELECT id FROM users WHERE username = '%s'" % escape(username))
    row = cur.fetchone()
    if row is None:
        cur.execute("INSERT INTO users (username) VALUES ('%s')" % escape(username))
        cur.execute("SELECT id FROM users WHERE username = '%s'" % escape(username))
        row = cur.fetchone()
    return row[0]
```

这里的escape就是一个格式转换，把'变成''，主要就是sql和py和JSON格式都不一样，没招，这部分提取就是先查再插最后查，查是看有没有，没有才能插，因为索引是only，插错了要报错，所以确认过后再插

#### HTTP层

```python
def main():
    init_db()                      # 建表、补列、造演示账号
    http_server = WebServer((HOST, PORT), Handler)
    http_server.serve_forever()    # 一直阻塞，等请求

def init_db():
    init_tables()          # server.py：建库建表
    ensure_auth_schema()   # 给老库补 display_name / password_hash 列
    seed_demo_user()       # 保证 demo / tarot2026 能登录
```

```python
PBKDF2_SALT = b"xingxun-2026"
PBKDF2_ITER = 200000

def hash_password(password):
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 PBKDF2_SALT, PBKDF2_ITER).hex()
    return "pbkdf2$" + digest

def verify_password(password, stored):
    if stored.startswith("pbkdf2$"):
        expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),PBKDF2_SALT, PBKDF2_ITER).hex()
        return hmac.compare_digest(stored[7:], expected)
    return hmac.compare_digest(
        hashlib.sha256(password.encode("utf-8")).hexdigest(), stored)
```

这里面设置PBKDF2_SALT,主要是为了打乱密码本身顺序，同一个密码算出的值是一样的，随机加入这个设置值，会让本来一样的密码不一样，加一层保险，前缀拼了一个pbkdf2$是因为之前密码设置是用其他格式适用的，这里是加分辨，最后返回值给了个hmac.compare_digest方法，这个查出来大概意思就是比较两个字符串或者对象一不一样的函数，= =也可以实现，但是= =会是第一个字符不对就返回，攻击者可以慢慢尝试看时间变化，从而试出来密码

```python
def register_user(data):
    username = str(data.get("username", "")).strip()
    display_name = str(data.get("display_name") or "").strip() or username
    password = str(data.get("password", ""))
    # 校验
    if len(username) < 2: raise ValueError("用户名至少需要 2 个字符")
    if len(password) < 6: raise ValueError("密码至少需要 6 个字符")
    # 查重
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cur.fetchone() is not None: raise UserExists("这个用户名已被使用")
    # 插入
    cur.execute("INSERT INTO users (username, display_name, password_hash) "
                "VALUES (%s, %s, %s)", (username, display_name, hash_password(password)))
    # 回读
    cur.execute("SELECT username, display_name, created_at FROM users WHERE id = %s",
                (cur.lastrowid,))
    return user_payload(cur.fetchone())
```

前面就是代码字面意思，看用户名，昵称，密码，是不是都是字符串且不带空格，看长度满不满足要求，然后判断库中有没有对应的重复的id，没有的话就insert进去，然后再确认一遍，这个确认一遍主要是为了让py也知道信息已经到位了

```python
def login_user(data):
    cur.execute("SELECT username, display_name, created_at, password_hash "
                "FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if row is None or not verify_password(password, row[3]):
        raise AuthFailed("用户名或密码不正确，请重新输入。")
    return user_payload(row)
```

这里就是一个判断，用with也可以，即用即退，不用with提早close，不然就占一个位置

```python
TOKEN_SECRET = b"xingxun-dev-token-secret-change-me"
TOKEN_TTL = 7 * 24 * 3600        # 7 天

def make_token(username):
    payload = "%s|%d" % (username, int(time.time()) + TOKEN_TTL)
    raw = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(TOKEN_SECRET, raw.encode(), hashlib.sha256).hexdigest()[:32]
    return raw + "." + sig

def read_token(token):
    raw, sig = token.split(".", 1)
    expect = hmac.new(TOKEN_SECRET, raw.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expect): return ""     # 被改过
    payload = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
    username, exp = payload.rsplit("|", 1)
    if int(exp) < int(time.time()): return ""              # 过期了
    return username
```

这一段主要是校验令牌，前面是做base64编码，可以去编码网站破解，所以没存密码，后面是做签名，大概就是一个验证流程，看传输的内容是否变化，这一块不太懂，只能这么解释

```python
def save_history(data):
    conn = get_conn(); cur = conn.cursor()
    try:
        user_id = get_user_id(cur, username)
        cur.execute("INSERT INTO history (user_id, question, method, hexagram, result) "
                    "VALUES (%s, %s, %s, %s, %s)", (user_id, question, method, hexagram, result))
        record_id = cur.lastrowid
        divination_id = insert_divination(cur, _divination_fields(...))
        conn.commit()          # ← 两条一起提交
    except Exception:
        conn.rollback()        # ← 一起回滚
        raise
    finally:
        cur.close(); conn.close()
```

这个也比较明显，就是往库里插值，一次插两个，上面的history和下面的divination，中间有个lastrowid方法，主要是看一下auto-increment key，读取之后就能拿到新id，然后为什么try下面是两条数据，history和divination要存一起存，因为这两个的内容基本是一样的，只不过一个是string，一个是JSON，要保证数据一一对应，所以两个对象一起try，divination也做了截断，这里就不贴代码了，截断就是怕内容太多，可能会出现插入失败

```python
def list_history(username="", limit=50):
    sql = ("SELECT h.id, u.username, h.question, h.method, h.hexagram, "
           "       h.result, h.created_at "
           "FROM history h JOIN users u ON u.id = h.user_id ")
    if username != "":
        sql += "WHERE u.username = %s "
    sql += "ORDER BY h.id DESC LIMIT %s"
```

这里就相当于是sql代码，就是来查询历史，join连这两个表主要是history只有数字，用户名再user里，所以要连user查到string

```python
def history_payload(item, username):
    reading = json.loads(item["result"]) if item["result"] else {}
    reading["id"] = str(reading.get("id") or item.get("id", ""))
    reading["username"] = username
    reading.setdefault("spreadName", item.get("hexagram") or "")
    reading["createdAt"] = reading.get("createdAt") or to_iso(item["created_at"])
    return reading
```

这个就是换格式，用json.loads，因为给前端要用对象，库里只有JSON，所以这里做一下转换，然后命名格式换不换其实大差不差，只是方便他人而已，我们要做好人

```python
path == "/"                 → 返回 index.html
path == "/api/history"      → 查历史（带 token 就只查自己）
path == "/api/divinations"  → 查结构化记录
path == "/api/health"       → SELECT 1，验证数据库活着
否则                         → 404 {"ok": false, "error": "接口不存在"}
# 第 525 行  do_POST
path == "/api/users"                    → 写入用户
path in ("/api/auth/register", "/api/register")  → 注册
path in ("/api/auth/login", "/api/login")        → 登录
path == "/api/auth/logout"              → 登出（无状态，直接回 ok）
path == "/api/history"                  → 写入一次占卜
path in ("/api/divinations", "/divinations")     → 直接写 divinations
```

这个就是配路径了，和这一部分的第一块代码差不多，我不太懂，这种就是照抄就完事了

```python
def do_OPTIONS(self):
    self.send_response(204)
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    self.end_headers()
```

大概意思就是来请求，浏览器请求过来，他带了自定义头或者JSON，会告诉服务器，问服务器能不能带这些内容，服务器回话能带，才能请求成功，不然浏览器就不发真请求，相当于是先试一试，不行就拜拜，行就真给你，跟http握手是类似的，*在这个里面就不是占位或者是分隔什么的，他跟正则类似，就是直接允许所有来源

```python
class WebServer(ThreadingHTTPServer):
    # Windows 下默认的 SO_REUSEADDR 会让第二个进程也能绑定 8000，
    # 请求被旧进程分走就会出现"数据时好时坏"。这里禁止重复绑定。
    allow_reuse_address = False
```

正常情况是允许多进程的，但是我们这个进程都在端口上，加入两个进程都进来了，那么数据到底给谁是一个问题，所以干脆只允许一个进程进来

#### 前端

```javascript
function configureRemote(settings) {
  configuration = {
    enabled: settings?.persistenceMode === 'mysql',
    baseUrl: String(settings?.accountApiUrl || '').trim().replace(/\/+$/, ''),
  }
}
function isRemoteEnabled() { return configuration.enabled }
```

这一部分内容都是js，属于是陌生地带，enabled对应浏览器上的本地演示那一块开关，baseurl就是输入框内地址，最后的isremoteenabled大概就是一个判定，判定后面的return，enabled开了就走后端，没开就走那个演示

```JavaScript
async function remoteRequest(path, options = {}) {
  if (!configuration.enabled) throw new Error('尚未启用 MySQL 账号与历史存储。')
  if (!/^https?:\/\//.test(configuration.baseUrl)) throw new Error('账号与历史服务地址尚未正确配置。')
  const { method = 'GET', body, token = '', timeoutMs = 20000 } = options
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort('timeout'), timeoutMs)
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(`${configuration.baseUrl}${path}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
    signal: controller.signal,
  })
  const data = await response.json().catch(() => null)
  if (!response.ok || data?.ok === false) throw new Error(data?.error || ...)
  return data
}
```

前两个主要就是判断类型输出错误情况，enabled跟前面代码是一样的，baseurl同理，后面相当于定义变量或者对象，然后做判断，拼地址，发送请求，等待请求，相应请求，对应的就是那个response和await，前面定义的内容放在里面就是保障请求，timer就是超时就中断，header部分就是判断token，大多是含义就是一个对照判断，只是js长得很复杂，但是逻辑很简单

```javascript
async login(username, password) {
    if (isRemoteEnabled()) {
      const data = await remoteRequest('/api/auth/login', {
        method: 'POST', body: { username: username.trim(), password } })
      return saveRemoteSession(data)
    }
    // 本地演示模式：用 localStorage 里的用户表比对
    const passwordHash = await hashPassword(password)
    ...
}

function saveRemoteSession(data) {
  if (!data?.user?.username || typeof data.token !== 'string' || !data.token)
    throw new Error('账号服务未返回有效的登录信息。')
  sessionStorage.setItem(TOKEN_KEY, data.token)
  writeStorage(SESSION_KEY, data.user)
  return data.user
}
```

这部分就是判断用户名是否存在，token是否存在，不为空，不满足就报错，跟前面差不多，意思就还是比对信息，然后请求，等待，回复，基本大差不差

```javascript
async create(input) {
    const reading = { ...normalize(input), id: createId('reading'), createdAt: ... }
    if (!isRemoteEnabled()) { 写本地; return reading }
    const token = authService.getToken()
    return serial(async () => {
      const data = await remoteRequest('/api/history', {
        method: 'POST', token,
        body: { question: reading.question, method: reading.method,
                hexagram: reading.spreadName || '', result: JSON.stringify(reading) },
      })
      if (!data.reading?.id) throw new Error('历史服务未返回已保存的档案。')
      ...写本地缓存...
    })
}
```

这部分就是把历史写入库中，从const data开始，就是一个请求节点，写入后在缓存，判断语句就是告诉如果没有写入，给错误，后续缓存他就没有存实在的记录，如果缓存在前，就会先存记录，哪怕他没有，前面return的serial就是处理并发，让请求排队，serial这个看是定义的方法还是原生的方法，可查，json.stringify跟py里的json.loads或者dumps一样，没有什么区别

```javascript
async function hashPassword(password) {
  if (globalThis.crypto && globalThis.crypto.subtle && globalThis.crypto.subtle.digest) {
    try {
      const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(password))
      return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2,'0')).join('')
    } catch (e) { }
  }
  return sha256HexSync(password)  
}
```

这一块就是密码编码，以防被取走，其实py做也可以

#### MySQL

这部分基本就是纯键纯插纯取，基本就是固定代码提取

```mysql
1. SELECT id FROM users WHERE username = %s
   → 拿到 user_id（没有就新建一行用户）

2. INSERT INTO history (user_id, question, method, hexagram, result) VALUES (...)
   → 得到 record_id

3. INSERT INTO divinations (user_id, method, topic, question, board_text, answer)
   → 得到 divination_id

4. COMMIT
   → 三条语句一起生效
```

```mysql
index idx_user (user_id),      -- 按用户查历史时用
index idx_time (created_at)    -- 按时间排序时用
```

```mysql
GRANT SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES
ON divination_simple.* TO 'xingxun_app'@'%';
```

```mysql
docker exec -it xingxun-mysql mysql -u root -p

USE divination_simple;
SHOW TABLES;                                  -- 三张表
DESCRIBE users;                               -- 看字段类型
SELECT id, username, created_at FROM users;    -- 看用户
SELECT id, user_id, method, LEFT(question,20) FROM history ORDER BY id DESC LIMIT 5;
SELECT id, user_id, topic, LEFT(answer,30) FROM divinations ORDER BY id DESC LIMIT 5;
```

这一块大概只需要注意到不同表中的id字段重复了要注意他的类型等问题，然后power shell这种终端类可能只用gbk，注意改成utf8即可

### 对话流代码

| 节点类型   | 数量 | 作用                                  |
| ---------- | ---- | ------------------------------------- |
| 开始节点   | 1    | 接受用户输入和外部参数                |
| 问题分类器 | 1    | 判断用户想用那种占卜方式              |
| 条件分支   | 6    | 按route、按method、按日期是否有效分流 |
| 代码节点   | 10   | 起盘、路由、历史、格式转换            |
| 变量赋值   | 10   | 把结果写进会话变量                    |
| 知识检索   | 6    | 每种方法一个知识库                    |
| 解读模型   | 6    | 每种方法一套专用提示词                |
| 直接回复   | 7    | 缺参数提示、引导语、最终回答          |
| 参数提取器 | 2    | 从自然语言提取日期和时辰              |
| 变量聚合器 | 1    | 取第一个非空结果往下传                |

| 节点名           | 输入                                            | 输出                     |
| ---------------- | ----------------------------------------------- | ------------------------ |
| 输出加固判断     | query,pending,board                             | route                    |
| 提取关键字       | query                                           | topic                    |
| 操牌（塔罗）     | query,topic                                     | board,board_text         |
| 操卦（六爻）     | query,topic                                     | board,board_text         |
| 黄历计算         | query,topic                                     | board,board_text         |
| 星座计算         | query,topic                                     | board,board_text,ok,hint |
| 转换日历（八字） | birth_date, birth_time, gender, query, topic    | board,board_text,ok,hint |
| 紫薇换算         | lunar_year/month/day, hour_index, gender, topic | board,board_text,ok,hint |
| 拉取历史记录     | history, question, answer                       | new_history              |
| 格式转换         | v（聚合器输出）                                 | answer                   |

#### 输出加固判断

```python
def main(query: str, pending: str = "", board: str = "") -> dict:
    q = str(query or "").strip()
    p = str(pending or "").strip()
    b = str(board or "").strip()

    METHOD_WORDS = ["塔罗", "六爻", "八字", "紫微", "星座", "抽牌", "摇卦", "起卦", "换一种", "换个方式"]
    CHITCHAT = ["你好", "您好", "在吗", "谢谢", "多谢", "再见", "拜拜", "好的", "嗯", "哈哈"]

    if any(k in q for k in METHOD_WORDS):
        return {"route": ""}

    if any(q.startswith(k) for k in CHITCHAT) or len(q) <= 2:
        return {"route": ""}

    if p in ("bazi", "ziwei", "astrology"):
        return {"route": p}

    if b:
        return {"route": "followup"}

    return {"route": ""}
```

前三行就是去空格，or ''是怕query这种为空，要给空字符串，纯空就是none，要报错，method_words就是记忆方法名字，chitchat是判断无关语言，让后续分类器让他走其他分支，引导用户输入，后面的if，q取用户输入，k遍历列表，判断是否对应，然后输出，第二个if判断输入语句是不是无关语言，由于语言分类少，所以加了一步len(q)的判断，后面两个if就是判断pending和board当中有没有值，有的话给return，没有就给''，这里只有三个方法是因为只有这三个方法需要用户信息，py是从上向下执行，所以一定会先判断pending有没有值，有的话就不走第四个if的追问

#### 提取关键字

```python
def main(query: str) -> dict:
    q = (query or "").strip().lower()

    MARRIAGE = ["姻缘", "婚姻", "感情", "恋爱", "脱单", "结婚", "前任",
                "暧昧", "分手", "对象", "伴侣", "桃花", "复合", "相亲"]
    MATTER = ["事业", "工作", "考试", "跳槽", "升职", "搬家", "搬迁",
              "合作", "签约", "项目", "求职", "面试", "调动", "创业", "offer"]
    FORTUNE = ["运势", "运气", "财运", "健康", "流年", "平安", "灾", "病"]

    topic = ""
    if not q or len(q) < 2:
        return {"topic": ""}

    for k in MARRIAGE:
        if k in q:
            topic = "marriage"
            break
    ...（MATTER、FORTUNE 同样的循环）

    return {"topic": topic}
```

第一行的strip跟之前一样，main函数取了变量类型，三个列表定义不同的占卜方向，定义话题topic，最后返回就是从中取的值，循环就很直白，判断用户输入长度，太少了就不输出话题，丢给后面节点，会进入引导分支，如果长度差不多够，就提取匹配，有就输出，然后停止循环，没有就还是''

#### 操牌

```python
MAJOR = ["愚者", "魔术师", "女祭司", "女皇", "皇帝", "教皇", "恋人", "战车",
         "力量", "隐士", "命运之轮", "正义", "倒吊人", "死神", "节制", "恶魔",
         "高塔", "星星", "月亮", "太阳", "审判", "世界"]
SUITS = ["权杖", "圣杯", "宝剑", "星币"]
RANKS = ["Ace", "2", ..., "国王"]
POSITIONS = ["过去", "现在", "未来"]

def build_deck():
    deck = [{"card": c, "arcana": "major"} for c in MAJOR]
    for s in SUITS:
        for r in RANKS:
            deck.append({"card": s + r, "arcana": "minor"})
    return deck

def main(query: str, topic = '') -> dict:
    seed = int(time.time() * 1000)
    rng = random.Random(seed)
    deck = build_deck()
    rng.shuffle(deck)
    cards = []
    for i, pos in enumerate(POSITIONS):
        c = deck[i]
        cards.append({"pos": pos, "card": c["card"], "arcana": c["arcana"],
                      "orientation": rng.choice(["upright", "reversed"])})
    board = {"method": "tarot", "topic": topic, "question": query,
             "spread": {"id": "three_card", "name": "三牌阵"}, "cards": cards, "seed": seed}
    ...
    return {"board": json.dumps(board, ensure_ascii=False), "board_text": "\n".join(lines)}
```

这里的主要是塔罗牌构建，build_deck就是遍历抽牌，前面变量定义好了之后直接循环抽取即可，把可能性都容纳进return的deck，main里面定义数据类型，设置随机数种子seed，用random.Random是直接取一个随机数，不会变，保证这一个流程内是稳定的，如果直接random.shuffle会直接打乱deck的排序方式，调一次打乱一次，是有可能重复的，seed也可能重复，但是我们在之前定义int(time.time()*1000)是毫秒时间戳，不会重复，调用的时候是当时的节点，把seed放进board就可以回头查看，可以复现，enumerate是建立索引，i是索引，pos是对应的值，这里就把deck中的卡牌放进cards，当中的rng.choice是随机取upright或者reversed,这里要单独做随机，不然索引决定了正逆就固定了，不会改变，这不符合情况，返回board和board_text，一个对象，一个JSON，dumps就是转JSON

#### 操卦

```python
TRIGRAM = {
    (1, 1, 1): "乾", (1, 1, 0): "兑", (1, 0, 1): "离", (1, 0, 0): "震",
    (0, 1, 1): "巽", (0, 1, 0): "坎", (0, 0, 1): "艮", (0, 0, 0): "坤",
}
ORDER = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]
NAMES = {
    "乾": ["乾", "履", "同人", "无妄", "姤", "讼", "遁", "否"],
    ...（共 8 行，构成 8×8 = 64 卦名表）
}

def main(query: str, topic: str = "") -> dict:
    seed = int(time.time() * 1000)
    rng = random.Random(seed)

    tosses = []
    for _ in range(6):
        coins = [3 if rng.random() < 0.5 else 2 for _ in range(3)]
        tosses.append(sum(coins))

    ben  = [1 if t in (7, 9) else 0 for t in tosses]
    bian = [(1 - b) if t in (6, 9) else b for t, b in zip(tosses, ben)]
    dong = [i + 1 for i, t in enumerate(tosses) if t in (6, 9)]
```

前面做定义，然后函数类型定义，seed和rng同上，因为铜钱只有正反面，所以rng.random<0.5取一半的概率，然后正面3，反面2，三枚铜钱的和就是6，7，8，9，然后摇6次，后面的ben和bian就是本卦变卦，ben就是7，9为阳，bian是6阳，9阴，比较好理解

#### 黄历

```python
def parse_target(q):
    t = str(q or "")
    today = date.today()
    if "大后天" in t:  return today + timedelta(days=3), False
    if "后天" in t:    return today + timedelta(days=2), False
    if "明天" in t:    return today + timedelta(days=1), False
    if "昨天" in t:    return today - timedelta(days=1), True
    m = re.search(r"(\d{4})\D{1,2}(\d{1,2})\D{1,2}(\d{1,2})", t)   # 2026-11-07
    if m: return date(...), False
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})", t)                 # 11月7日
    if m: return date(today.year, ...), False
    return today, False
```

主要注意判断顺序，大后天包含后天，所以只能先大后天，不然问大后天也会匹配后天，日期就差一天，中文命制一定要注意，然后正则匹配，忘记了就查

```python
a, y2, m2 = (14 - mo) // 12, y + 4800 - a, mo + 12 * a - 3
jdn = d + (153*m2+2)//5 + 365*y2 + y2//4 - y2//100 + y2//400 - 32045
dg = (jdn + DAY_OFFSET) % 10      # 日干
dz = (jdn + DAY_OFFSET) % 12      # 日支

mz = mo % 12                       # 月建
if d < TERM.get(mo, 6):            # 节气前算上个月
    mz = (mo - 1) % 12

name = JIANCHU[(dz - mz) % 12]     # 建除十二神
chong_zhi = (dz + 6) % 12          # 冲：地支对面
```

这一部分算建除十二神，干支公历的换算，主要是按照传统计算方法建立

#### 星座

```python
BOUNDS = [(1,20,"水瓶"), (2,19,"双鱼"), (3,21,"白羊"), ...]

def sun_sign(mo, d):
    for i in range(12, 0, -1):          # 从 12 月往 1 月倒着找
        bm, bd, name = BOUNDS[i - 1]
        if (mo, d) >= (bm, bd):
            return name
    return "摩羯"                        # 1 月 1–19 日落在摩羯
```

倒着找是因为正着找会差一个顺序，比如1，10是小于1，20的，水瓶的索引是0，前面没了，所以要倒着找，然后出问题只可能在摩羯位置，所以最后找不到直接返回摩羯

```python
if not parsed:
    return {"ok": False,
            "hint": "我需要你的出生日期（公历月日即可），比如「3月12日」或「1998年3月12日」。",
            "board": "", "board_text": ""}
```

没有参数的话，返回字典，ok后续分支有判断要引用，hint是输出的话，然后board和board_text设空

#### 八字

```python
def parse_date(s):
    m = re.search(r"(\d{2,4})\D+(\d{1,2})\D+(\d{1,2})", t)
    y = int(m.group(1))
    if y < 100:
        y += 2000 if y <= 30 else 1900        # 98 → 1998，08 → 2008
    if not (1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
        return None                            # 范围不合理就当没解析到

def parse_time(s):
    m = re.search(r"(\d{1,2})\s*[:：]\s*(\d{1,2})", t)     # 14:30
    ...
    SHICHEN = {"子": 23, "丑": 1, "寅": 3, ...}               # 子时 / 丑时
    ...
    m = re.search(r"(\d{1,2})\s*[点時时]", t)                 # 下午三点
    if any(w in t for w in ("下午", "晚上", "傍晚")) and h < 12: h += 12
```

跟前面一样，先正则日期，然后取年份，这里考虑两位数的年份输入，设置30的界限是因为现在是2026，输入20年一般是2020而不是1920，同理输入90年，肯定是1990，不可能是2090，然后定义合理范围，后续时间定义和日期定义类似，正则之后按照规定设定字典

```python
hz = ((hh + 1) // 2) % 12          # 小时 → 时辰序号（子=0）
hg = ((dg * 2) % 10 + hz) % 10      # 日干 → 时干

# 23 点 → (24)//2 = 12 % 12 = 0 → 子时
# 1 点  → (2)//2  = 1        → 丑时
```

定义时辰，注意转义字符，也可以手动定义，就是麻烦点，然后是五鼠遁，数学公式转换而已

```python
lines.append("（简化排盘，未含节气精算与真太阳时）")
```

声明边界

#### 紫薇

```python
yg = (y - 4) % 10        # 年干
yz = (y - 4) % 12        # 年支

ming = (2 + (m - 1) - h) % 12    # 命宫
shen = (2 + (m - 1) + h) % 12    # 身宫
```

数学表达式

```python
yin_gan = (yg * 2 + 2) % 10                  # 寅宫天干（五虎遁）
ming_gan = (yin_gan + (ming - 2) % 12) % 10   # 命宫天干
n = ganzhi_index(ming_gan, ming)               # 命宫干支在六十甲子里的序号
element = NAYIN[n // 2]                        # 纳音五行
ju = JU[element]                               # 五行 → 局数
```

```python
ZI_WEI_SERIES = [("紫微",0), ("天机",-1), ("太阳",-3), ("武曲",-4), ("天同",-5), ("廉贞",-8)]
TIAN_FU_SERIES = [("天府",0), ("太阴",1), ("贪狼",2), ("巨门",3),
                  ("天相",4), ("天梁",5), ("七杀",6), ("破军",10)]

def ziwei_branch(ju, day):
    borrow = (ju - day % ju) % ju          # 补到 ju 的整数倍还差几天
    quotient = ((day + borrow) // ju) % 12
    base = quotient - 1
    steps = base + borrow if borrow % 2 == 0 else base - borrow   # 偶加奇减
    return (2 + steps) % 12
```

```python
is_yang = yg % 2 == 0                     # 阳年干
male = str(gender).strip().lower() in ("male", "男")
forward = (is_yang and male) or (not is_yang and not male)   # 阳男阴女顺行

for i, name in enumerate(PALACES):
    step = i if not forward else (-i) % 12
    age_start = ju + step * 10
```

```python
"precision": "major_stars_with_sihua"
lines.append("（已排十四主星与生年四化，未排辅星与神煞）")
```

这一部分和八字类似，基本都是按照传统进行换算，都是数学的简单计算表达，反复验证即可

#### 拉取历史记录

```python
def main(history: str, question: str, answer: str) -> dict:
    raw = (history or "").strip()
    try:
        items = json.loads(raw) if raw.startswith("[") else []
    except Exception:
        items = []
    if not isinstance(items, list):
        items = []

    items.append({"q": question.strip(), "a": answer.strip()})
    items = items[-5:]          # ← 只留最近 5 轮
    return {"new_history": json.dumps(items, ensure_ascii=False)}
```

依旧是类型标注，然后清空格，由于JSON和string在模型中经常出错，所以用try，except，然后isinstance判断items是否是列表，也是因为有可能解析出错，后面[-5:]是只留最后五轮，以防上下文爆炸

#### 格式转换

```python
def main(v) -> dict:
    if isinstance(v, dict):
        for key in ("value", "output", "text", "result", "answer"):
            val = v.get(key)
            if isinstance(val, str) and val.strip():
                return {"answer": val}
        vals = [str(x) for x in v.values() if isinstance(x, (str, int, float))]
        return {"answer": "\n".join(vals)}
    if isinstance(v, list):
        return {"answer": "\n".join(str(x) for x in v)}
    return {"answer": str(v)}
```

轮询五个变量名，因为上游节点变量名不一样，所以干脆一格一格写，也不多，避免报错，后面格式转换跟前面输出string是类似的