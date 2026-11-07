"""Version-anchored conversations and personal mention inbox, not outbound messaging."""
from .contracts import register, S
from .model import require, uid, Fault

from .studio_targets import ANCHOR
register('studio_comment', {'work_id':S,'project_id':S,'state_id':S,'anchor':ANCHOR,'thread_id':S,
    'body':{'type':'string','minLength':1,'maxLength':4000},
    'mentions':{'type':'array','maxItems':20,'items':S}}, ['state_id','anchor','body','mentions'])
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
        self.allowed(actor,'record')
        c,d,state,pid=self._studio_target(s,actor,a)
        wid=c['id'] if c else None; anchor=a['anchor']
        require(a['body'].strip(),'invalid_input','Comment is empty')
        recipients=set(a['mentions'])
        for recipient in recipients:
            person=s['principals'].get(recipient)
            require(person and person.get('enabled',True),'invalid_input','Unknown mention recipient')
            self._dev_session(s,person,d['id']); self._continuity_state(s,person,state['id'])
        if a.get('thread_id'):
            t=self._dev_get(s,'studio_threads',a['thread_id'])
            require(t.get('work_id')==wid and t.get('project_id',pid)==pid and t['state_id']==state['id'] and t['anchor']==anchor,
                'invalid_input','Reply must keep original work, version and selection')
        else:
            # Serialized Core write: simultaneous first comments share one discussion.
            t=next((t for t in s.get('studio_threads',{}).values() if t.get('work_id')==wid and t.get('project_id',pid)==pid
                and t['state_id']==state['id'] and t['anchor']==anchor),None)
            if t is None:
                t=dict(id=uid('thread'),session_id=d['id'],subject_id=wid or pid,work_id=wid,project_id=pid,state_id=state['id'],
                    anchor=anchor,at=self.clock(),author=actor['id'])
                self._dev_save(s,fx,'studio_threads',t)
        m=dict(id=uid('message'),session_id=d['id'],subject_id=t['id'],thread_id=t['id'],body=a['body'],
            mentions=sorted(recipients),author=actor['id'],at=self.clock(),state_id=state['id'])
        self._dev_save(s,fx,'studio_messages',m)
        for recipient in recipients:
            item=dict(id=uid('mention'),session_id=d['id'],subject_id=recipient,work_id=wid,project_id=t.get('project_id'),state_id=state['id'],
                thread_id=t['id'],message_id=m['id'],at=self.clock(),read=False)
            self._dev_save(s,fx,'studio_notifications',item)
            n.append({'type':'studio_mention','target':d['id'],'recipient':recipient,'thread_id':t['id'],
                'state_id':state['id'],'work_id':wid,'zones':[d['zone']]})
        return m

    def cmd_studio_inbox(self,s,actor,a,fx,n,con):
        items=[]
        for item in s.get('studio_notifications',{}).values():
            if item['subject_id']!=actor['id']: continue
            t=s['studio_threads'][item['thread_id']]
            try: c,_,state,pid=self._studio_target(s,actor,{**item,'anchor':t['anchor']})
            except Fault: continue
            m=s['studio_messages'][item['message_id']]
            title=c['title'] if c else s['product_projects'][pid]['name']
            items.append({**item,'project_id':pid,'title':title,'body':m['body'],'author':m['author'],'anchor':t['anchor']})
        items.sort(key=lambda i:i['id']); items=[i for i in items if i['id']>a.get('after','')]; limit=a.get('limit',100)
        return {'items':items[:limit],'next':items[limit-1]['id'] if len(items)>limit else None}

    def cmd_studio_acknowledge(self,s,actor,a,fx,n,con):
        self.allowed(actor,'record'); item=self._dev_get(s,'studio_notifications',a['notification_id'])
        require(item['subject_id']==actor['id'],'unauthorized','Only the recipient may mark this mention read')
        self._dev_session(s,actor,item['session_id']); item['read']=True
        return self._dev_save(s,fx,'studio_notifications',item)
