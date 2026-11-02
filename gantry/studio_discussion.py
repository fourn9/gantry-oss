"""Version-anchored conversations and personal mention inbox, not outbound messaging."""
from .contracts import register, S
from .model import require, uid, Fault

ANCHOR={'type':'object','properties':{'kind':{'enum':['work','cad','code']},'path':S,'hash':S,
    'part':S,'line':{'type':'integer','minimum':1}},'required':['kind'],'additionalProperties':False}
register('studio_comment', {'work_id':S,'state_id':S,'anchor':ANCHOR,'thread_id':S,
    'body':{'type':'string','minLength':1,'maxLength':4000},
    'mentions':{'type':'array','maxItems':20,'items':S}}, ['work_id','state_id','anchor','body','mentions'])
register('studio_inbox', {'after':S,'limit':{'type':'integer','minimum':1,'maximum':100}})
register('studio_acknowledge', {'notification_id':S}, ['notification_id'])


class StudioDiscussionMixin:
    def _studio_threads(self,s,wid,sid):
        threads=[dict(t) for t in s.get('studio_threads',{}).values() if t['work_id']==wid and t['state_id']==sid]
        messages={t['id']:[] for t in threads}
        for m in s.get('studio_messages',{}).values():
            if m['subject_id'] in messages: messages[m['subject_id']].append(m)
        for t in threads:
            t['messages']=sorted(messages[t['id']],key=lambda m:(m['at'],m['id']))
        return sorted(threads,key=lambda t:(t['at'],t['id']))

    def _studio_discussion_index(self,s,actor,change):
        allowed={}
        result=[]
        messages={}
        for m in s.get('studio_messages',{}).values():
            messages.setdefault(m['thread_id'],[]).append((m['at'],m['id']))
        for t in s.get('studio_threads',{}).values():
            if t['work_id']!=change['id']: continue
            sid=t['state_id']
            if sid not in allowed:
                try: self._studio_state(s,actor,change,sid); allowed[sid]=True
                except Fault: allowed[sid]=False
            if not allowed[sid]: continue
            ids=sorted(messages.get(t['id'],[]))
            result.append({'id':t['id'],'state_id':sid,'anchor':t['anchor'],
                'message_count':len(ids),'last_message_id':ids[-1][1] if ids else None})
        return sorted(result,key=lambda t:t['id'])

    def cmd_studio_comment(self,s,actor,a,fx,n,con):
        self.allowed(actor,'record'); c,d=self._studio_work(s,actor,a['work_id'])
        state=self._studio_state(s,actor,c,a['state_id']); anchor=a['anchor']; kind=anchor['kind']
        require(a['body'].strip(),'invalid_input','Comment is empty')
        allowed={'kind'} if kind=='work' else {'kind','path','hash','line'} if kind=='code' else {'kind','path','hash','part'}
        require(set(anchor)<=allowed,'invalid_input','Anchor fields do not match selection kind')
        if kind!='work':
            path=anchor.get('path'); info=self._manifest(s,state['snapshot']).get(path)
            require(info and info['hash']==anchor.get('hash'),'invalid_input','Anchor does not match saved file and version')
            if kind=='code':
                require(info['size']<=262144,'invalid_input','File too large for line anchoring')
                try: text=b''.join(self.store.verified_parts(info)).decode('utf-8')
                except UnicodeDecodeError: raise Fault('invalid_input','Code line anchor requires UTF-8 text')
                require('\x00' not in text and 1<=anchor.get('line',0)<=len(text.splitlines()),'invalid_input','Line does not exist')
            else:
                # A file is the stable selectable mesh part until a tool supplies native subpart IDs.
                require(anchor.get('part')==path,'invalid_input','CAD selection must identify its saved mesh file')
                require(path.lower().endswith(('.stl','.obj')),'invalid_input','Part preview is unsupported')
        recipients=set(a['mentions'])
        for pid in recipients:
            person=s['principals'].get(pid)
            require(person and person.get('enabled',True),'invalid_input','Unknown mention recipient')
            self._dev_session(s,person,d['id']); self._continuity_state(s,person,state['id'])
        if a.get('thread_id'):
            t=self._dev_get(s,'studio_threads',a['thread_id'])
            require(t['work_id']==c['id'] and t['state_id']==state['id'] and t['anchor']==anchor,
                'invalid_input','Reply must keep original work, version and selection')
        else:
            # Serialized Core write: simultaneous first comments share one discussion.
            t=next((t for t in s.get('studio_threads',{}).values() if t['work_id']==c['id']
                and t['state_id']==state['id'] and t['anchor']==anchor),None)
            if t is None:
                t=dict(id=uid('thread'),session_id=d['id'],subject_id=c['id'],work_id=c['id'],state_id=state['id'],
                    anchor=anchor,at=self.clock(),author=actor['id'])
                self._dev_save(s,fx,'studio_threads',t)
        m=dict(id=uid('message'),session_id=d['id'],subject_id=t['id'],thread_id=t['id'],body=a['body'],
            mentions=sorted(recipients),author=actor['id'],at=self.clock(),state_id=state['id'])
        self._dev_save(s,fx,'studio_messages',m)
        for pid in recipients:
            item=dict(id=uid('mention'),session_id=d['id'],subject_id=pid,work_id=c['id'],state_id=state['id'],
                thread_id=t['id'],message_id=m['id'],at=self.clock(),read=False)
            self._dev_save(s,fx,'studio_notifications',item)
            n.append({'type':'studio_mention','target':d['id'],'recipient':pid,'thread_id':t['id'],
                'state_id':state['id'],'work_id':c['id'],'zones':[d['zone']]})
        return m

    def cmd_studio_inbox(self,s,actor,a,fx,n,con):
        items=[]
        for item in s.get('studio_notifications',{}).values():
            if item['subject_id']!=actor['id']: continue
            try:
                c,_=self._studio_work(s,actor,item['work_id']); self._studio_state(s,actor,c,item['state_id'])
            except Fault: continue
            m=s['studio_messages'][item['message_id']]; t=s['studio_threads'][item['thread_id']]
            items.append({**item,'title':c['title'],'body':m['body'],'author':m['author'],'anchor':t['anchor']})
        items.sort(key=lambda i:i['id']); items=[i for i in items if i['id']>a.get('after','')]; limit=a.get('limit',100)
        return {'items':items[:limit],'next':items[limit-1]['id'] if len(items)>limit else None}

    def cmd_studio_acknowledge(self,s,actor,a,fx,n,con):
        self.allowed(actor,'record'); item=self._dev_get(s,'studio_notifications',a['notification_id'])
        require(item['subject_id']==actor['id'],'unauthorized','Only the recipient may mark this mention read')
        self._dev_session(s,actor,item['session_id']); item['read']=True
        return self._dev_save(s,fx,'studio_notifications',item)
