from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
from datetime import datetime, timedelta
import sqlite3, os, re, hashlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DB_DIR, 'analytics.db')
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pulsedesk-local-secret-change-me')

def db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'Analyst');
    CREATE TABLE IF NOT EXISTS articles(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, source TEXT NOT NULL, category TEXT NOT NULL, content TEXT NOT NULL, published_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New');
    CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, created_at TEXT NOT NULL);
    ''')
    if not conn.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        conn.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)', ('admin', hash_password('admin123'), 'Administrator'))
    if not conn.execute('SELECT 1 FROM articles LIMIT 1').fetchone():
        seed = [
            ('Metro expansion opens a new transit corridor','City Desk','Transport','A new metro corridor has entered the next phase of operations, connecting residential areas with major business districts. The project includes coordinated traffic monitoring and passenger information systems.'),
            ('City launches open mobility data dashboard','Civic Data','Technology','A public mobility dashboard publishes transport demand, congestion patterns and travel-time information for researchers, planners and citizens.'),
            ('Universities increase practical artificial intelligence programs','Campus Wire','Education','Universities are expanding project-based artificial intelligence and data science programs with practical laboratories, industry projects and applied analytics.'),
            ('Transit operators test live route monitoring tools','Urban Today','Transport','Transport teams are using live route monitoring tools to identify recurring bottlenecks, coordinate field teams and improve service visibility.'),
            ('Digital public-service platforms add smarter search','Tech Journal','Technology','Public-service platforms are improving search and retrieval so users can find announcements, service information and related updates faster.'),
            ('Community groups create verified local information hubs','Civic Post','Community','Community organizations are combining verified announcements, local events and public-service updates into searchable information hubs.'),
            ('Repeated reports make event monitoring difficult','Data Review','Media','Newsrooms increasingly use duplicate detection and story grouping to reduce repeated reports while preserving source attribution.'),
            ('Data teams explore faster text pattern matching','Research Daily','Technology','Analytics teams are applying efficient text matching to search large collections of articles, posts and reports.'),
            ('Transport authority publishes a second mobility update','City Desk','Transport','The transport authority released another update about the metro corridor, route monitoring, passenger information and congestion coordination.'),
            ('New city buses connect the outer residential belt','Urban Today','Transport','A new set of city bus routes is connecting outer residential areas with metro stations and major employment centers.'),
            ('Local colleges open a shared innovation studio','Campus Wire','Education','Several colleges opened a shared innovation studio for student projects, applied analytics and community-focused technology work.'),
            ('Civic teams publish weekend road closure updates','Civic Post','Community','Civic teams published road closure information and alternate routes for weekend maintenance work across several neighborhoods.')]
        now = datetime.now()
        for i, (title,source,category,content) in enumerate(seed):
            published=(now-timedelta(minutes=i*11+3)).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('INSERT INTO articles(title,source,category,content,published_at,status) VALUES(?,?,?,?,?,?)',(title,source,category,content,published,'New'))
    conn.commit(); conn.close()

def log_activity(action):
    conn=db(); conn.execute('INSERT INTO activity(action,created_at) VALUES(?,?)',(action,datetime.now().strftime('%Y-%m-%d %H:%M:%S'))); conn.commit(); conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if 'user' not in session: return redirect(url_for('login'))
        return fn(*args,**kwargs)
    return wrapped

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form.get('username','').strip(); password=request.form.get('password','')
        conn=db(); user=conn.execute('SELECT * FROM users WHERE username=? AND password_hash=?',(username,hash_password(password))).fetchone(); conn.close()
        if user:
            session['user']=user['username']; session['role']=user['role']; log_activity('User signed in'); return redirect(url_for('dashboard'))
        flash('Invalid username or password.','error')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

# Internal text intelligence. The UI never exposes implementation names.
def normalize(text): return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9\s]',' ',(text or '').lower())).strip()
def kmp_lps(pattern):
    p=normalize(pattern); lps=[0]*len(p); length=0; i=1
    while i<len(p):
        if p[i]==p[length]: length+=1; lps[i]=length; i+=1
        elif length: length=lps[length-1]
        else: i+=1
    return lps

def kmp_search(text,pattern):
    t,p=normalize(text),normalize(pattern)
    if not p:return []
    lps=kmp_lps(p); ans=[]; i=j=0
    while i<len(t):
        if t[i]==p[j]: i+=1; j+=1
        if j==len(p): ans.append(i-j); j=lps[j-1]
        elif i<len(t) and t[i]!=p[j]: j=lps[j-1] if j else 0; i+=1 if j==0 else 0
    return ans

def suffix_array(s):
    s=normalize(s); n=len(s)
    if not n:return []
    sa=list(range(n)); rank=[ord(c) for c in s]; k=1
    while k<n:
        sa.sort(key=lambda i:(rank[i],rank[i+k] if i+k<n else -1)); new=[0]*n
        for j in range(1,n):
            a,b=sa[j-1],sa[j]; pa=(rank[a],rank[a+k] if a+k<n else -1); pb=(rank[b],rank[b+k] if b+k<n else -1); new[b]=new[a]+(pa<pb)
        rank=new
        if rank[sa[-1]]==n-1:break
        k*=2
    return sa

def lcp_array(s,sa):
    n=len(s); rank=[0]*n
    for i,p in enumerate(sa):rank[p]=i
    lcp=[0]*max(0,n-1); h=0
    for i in range(n):
        r=rank[i]
        if r==n-1:h=0; continue
        j=sa[r+1]
        while i+h<n and j+h<n and s[i+h]==s[j+h]:h+=1
        lcp[r]=h
        if h:h-=1
    return lcp

def lcp_similarity(a,b):
    a,b=normalize(a),normalize(b)
    if not a or not b:return 0.0
    s=a+'\x00'+b; split=len(a); sa=suffix_array(s); lcp=lcp_array(s,sa); best=0
    for i in range(len(sa)-1):
        x,y=sa[i],sa[i+1]
        if (x<split)!=(y<split):best=max(best,lcp[i])
    return round(best/max(1,min(len(a),len(b)))*100,1)

def edit_distance(a,b):
    a,b=normalize(a),normalize(b); prev=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        cur=[i]
        for j,cb in enumerate(b,1):cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(ca!=cb)))
        prev=cur
    return prev[-1]

def query_correction(q,vocabulary):
    q=normalize(q)
    if not q:return []
    ranked=[]
    for word in vocabulary:
        d=edit_distance(q,word)
        if d<=max(2,len(q)//2):ranked.append((d,word))
    return [w for _,w in sorted(ranked)[:6]]

def tokenize(text): return set(re.findall(r'[a-z0-9]{3,}',normalize(text)))
def jaccard(a,b):
    A,B=tokenize(a),tokenize(b); return len(A&B)/len(A|B) if A and B else 0

def cluster_articles(rows):
    parent=list(range(len(rows)))
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb:parent[rb]=ra
    for i in range(len(rows)):
        for j in range(i+1,len(rows)):
            if jaccard(rows[i]['content'],rows[j]['content'])>=0.16:union(i,j)
    groups={}
    for i,row in enumerate(rows):groups.setdefault(find(i),[]).append(row)
    return list(groups.values())

def max_flow(capacity,source,sink):
    n=len(capacity); total=0
    while True:
        parent=[-1]*n; parent[source]=source; q=[source]
        for u in q:
            for v,c in enumerate(capacity[u]):
                if parent[v]==-1 and c>0:
                    parent[v]=u; q.append(v)
                    if v==sink:break
            if parent[sink]!=-1:break
        if parent[sink]==-1:break
        aug=10**9; v=sink
        while v!=source:u=parent[v]; aug=min(aug,capacity[u][v]); v=u
        v=sink
        while v!=source:u=parent[v]; capacity[u][v]-=aug; capacity[v][u]+=aug; v=u
        total+=aug
    return total

@app.route('/')
@login_required
def dashboard():return render_template('dashboard.html',title='PulseDesk')
@app.route('/feed')
@login_required
def feed():return redirect(url_for('dashboard')+'#feed')
@app.route('/search')
@login_required
def search_page():return render_template('search.html',title='Search | PulseDesk')
@app.route('/duplicates')
@login_required
def duplicates_page():return redirect(url_for('dashboard')+'#similar')
@app.route('/clusters')
@login_required
def clusters_page():return redirect(url_for('dashboard')+'#trending')
@app.route('/moderation')
@login_required
def moderation_page():return redirect(url_for('dashboard')+'#review')

@app.route('/api/live')
@login_required
def api_live():
    conn=db(); rows=conn.execute('SELECT * FROM articles ORDER BY id DESC LIMIT 20').fetchall(); all_rows=conn.execute('SELECT * FROM articles ORDER BY id DESC').fetchall(); conn.close()
    cats={}; sources={}
    for r in all_rows:cats[r['category']]=cats.get(r['category'],0)+1; sources[r['source']]=sources.get(r['source'],0)+1
    return jsonify({'server_time':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'articles':[dict(r) for r in rows],'stories':len(all_rows),'sources':len(sources),'categories':len(cats),'categories_data':sorted(cats.items(),key=lambda x:x[1],reverse=True),'sources_data':sorted(sources.items(),key=lambda x:x[1],reverse=True)})
@app.route('/api/stats')
@login_required
def api_stats():return api_live()
@app.route('/api/articles')
@login_required
def api_articles():
    q=request.args.get('q','').strip(); category=request.args.get('category','').strip(); conn=db(); sql='SELECT * FROM articles'; params=[]; clauses=[]
    if q:clauses.append('(title LIKE ? OR content LIKE ? OR source LIKE ?)'); params += [f'%{q}%',f'%{q}%',f'%{q}%']
    if category:clauses.append('category=?'); params.append(category)
    if clauses:sql+=' WHERE '+' AND '.join(clauses)
    sql+=' ORDER BY id DESC'; rows=conn.execute(sql,params).fetchall(); conn.close(); return jsonify([dict(r) for r in rows])
@app.route('/api/search',methods=['POST'])
@login_required
def api_search():
    q=(request.get_json(force=True).get('query','') or '').strip(); conn=db(); rows=conn.execute('SELECT * FROM articles ORDER BY id DESC').fetchall(); conn.close()
    if not q:return jsonify({'query':'','count':0,'results':[],'suggestions':[]})
    results=[]
    for row in rows:
        hits=kmp_search(row['title']+' '+row['content'],q)
        if hits:results.append({**dict(row),'matches':len(hits),'snippet':row['content'][:240]+('...' if len(row['content'])>240 else '')})
    vocab=sorted(set(w for r in rows for w in re.findall(r'[a-z]{3,}',normalize(r['title']+' '+r['content'])))); suggestions=query_correction(q,vocab)
    return jsonify({'query':q,'count':len(results),'results':results[:50],'suggestions':suggestions})
@app.route('/api/related/<int:article_id>')
@login_required
def api_related(article_id):
    conn=db(); target=conn.execute('SELECT * FROM articles WHERE id=?',(article_id,)).fetchone(); rows=conn.execute('SELECT * FROM articles WHERE id!=?',(article_id,)).fetchall(); conn.close()
    if not target:return jsonify([]),404
    scored=[]
    for r in rows:
        score=max(lcp_similarity(target['content'],r['content']),round(jaccard(target['content'],r['content'])*100,1))
        if score>=10:scored.append((score,r))
    scored.sort(key=lambda x:x[0],reverse=True); return jsonify([{**dict(r),'similarity':s} for s,r in scored[:6]])
@app.route('/api/trending')
@login_required
def api_trending():
    conn=db(); rows=conn.execute('SELECT * FROM articles ORDER BY id DESC').fetchall(); conn.close(); output=[]
    for group in cluster_articles(rows):
        if len(group)<2:continue
        words=[]
        for r in group:words.extend(re.findall(r'[a-z]{4,}',normalize(r['title'])))
        stop={'with','from','that','this','into','city','new','live','more','news','about','opens','publishes'}; counts={w:words.count(w) for w in set(words) if w not in stop}
        label=' '.join(w.title() for w,_ in sorted(counts.items(),key=lambda x:x[1],reverse=True)[:2]) or group[0]['category']; output.append({'label':label,'count':len(group),'category':group[0]['category']})
    output.sort(key=lambda x:x['count'],reverse=True); return jsonify(output[:6])
@app.route('/api/similar')
@login_required
def api_similar():
    conn=db(); rows=conn.execute('SELECT * FROM articles ORDER BY id DESC').fetchall(); conn.close(); pairs=[]
    for i in range(len(rows)):
        for j in range(i+1,len(rows)):
            score=max(lcp_similarity(rows[i]['content'],rows[j]['content']),round(jaccard(rows[i]['content'],rows[j]['content'])*100,1))
            if score>=18:pairs.append({'a':rows[i]['title'],'b':rows[j]['title'],'score':score,'source_a':rows[i]['source'],'source_b':rows[j]['source']})
    return jsonify(sorted(pairs,key=lambda x:x['score'],reverse=True)[:12])
@app.route('/api/duplicates')
@login_required
def api_duplicates():return api_similar()
@app.route('/api/review')
@login_required
def api_review():
    conn=db(); rows=conn.execute("SELECT * FROM articles WHERE status IN ('New','Review') ORDER BY id DESC LIMIT 20").fetchall(); conn.close(); queue=len(rows); moderators=4; capacity=moderators*3
    cap=[[0]*(moderators+2) for _ in range(moderators+2)]
    for m in range(1,moderators+1):cap[0][m]=3; cap[m][moderators+1]=3
    assigned=min(queue,max_flow([r[:] for r in cap],0,moderators+1)); return jsonify({'queue':queue,'assigned':assigned,'capacity':capacity,'items':[dict(r) for r in rows[:8]]})
@app.route('/api/flow',methods=['POST'])
@login_required
def api_flow():return api_review()
@app.route('/api/add',methods=['POST'])
@login_required
def api_add():
    d=request.get_json(force=True); title=d.get('title','').strip(); content=d.get('content','').strip()
    if not title or not content:return jsonify({'ok':False,'message':'Headline and content are required.'}),400
    source=d.get('source','Manual Feed').strip() or 'Manual Feed'; category=d.get('category','General').strip() or 'General'; conn=db(); conn.execute('INSERT INTO articles(title,source,category,content,published_at,status) VALUES(?,?,?,?,?,?)',(title,source,category,content,datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'New')); conn.commit(); conn.close(); log_activity('New story added to the live stream'); return jsonify({'ok':True})
@app.route('/api/review/<int:article_id>',methods=['POST'])
@login_required
def api_review_item(article_id):
    status=(request.get_json(silent=True) or {}).get('status','Reviewed'); status=status if status in ('Reviewed','Flagged','New','Review') else 'Reviewed'; conn=db(); conn.execute('UPDATE articles SET status=? WHERE id=?',(status,article_id)); conn.commit(); conn.close(); return jsonify({'ok':True})
@app.route('/api/health')
def health():return jsonify({'status':'online'})

if __name__=='__main__':
    init_db(); app.run(debug=True,host='127.0.0.1',port=5000)
