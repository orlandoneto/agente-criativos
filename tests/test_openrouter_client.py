import asyncio
import base64
import io
import json
import time

import httpx
import pytest
from PIL import Image
from pydantic import BaseModel

from app import openrouter_client as router, gemini_client, image_gen, ia_sessao

M1='test/one:free'
M2='test/two:free'

def entry(model, modality='text', price='0'):
    return {'id':model, 'pricing':{'prompt':price,'completion':'0'},
            'architecture':{'output_modalities':[modality]},'supported_parameters':['response_format']}

@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(router,'OPENROUTER_API_KEY','dummy-not-a-real-secret')
    monkeypatch.setattr(router,'OPENROUTER_TEXT_MODELS',(M1,M2))
    monkeypatch.setattr(router,'OPENROUTER_IMAGE_MODELS',(M1,))
    monkeypatch.setattr(router,'_catalog',[entry(M1),entry(M2)])
    monkeypatch.setattr(router,'_catalog_until',time.monotonic()+999)
    monkeypatch.setattr(router,'_cooldown_until',0.0)
    monkeypatch.setattr(image_gen,'_avisar_img',lambda x:None)
    ia_sessao.reset()
    yield
    ia_sessao.reset()

def transport(monkeypatch, handler):
    real=httpx.AsyncClient
    def factory(**kwargs):
        assert kwargs['verify'] is not False and kwargs['follow_redirects'] is False
        return real(**kwargs,transport=httpx.MockTransport(handler))
    monkeypatch.setattr(router.httpx,'AsyncClient',factory)

def text_response(text='OK'):
    return httpx.Response(200,json={'choices':[{'message':{'content':text},'finish_reason':'stop'}]})

class Mini(BaseModel):
    x:int

def test_free_text_json_app_path(monkeypatch):
    calls=[]
    def handler(request):
        p=json.loads(request.content);calls.append(p['model'])
        assert p['provider']['allow_fallbacks'] is False
        assert p['provider']['max_price']=={'prompt':0,'completion':0}
        return text_response('{"x":1}')
    transport(monkeypatch,handler)
    monkeypatch.setattr(gemini_client,'_com_failover',lambda *a:pytest.fail('unexpected Gemini'))
    assert gemini_client.gerar_json('test',Mini).x==1
    assert calls==[M1] and ia_sessao.modelo_texto=='openrouter/'+M1

@pytest.mark.parametrize('status',[401,403,404,429,500,503])
def test_error_moves_without_same_model_retry(monkeypatch,status):
    calls=[]
    def handler(request):
        model=json.loads(request.content)['model'];calls.append(model)
        return httpx.Response(status,headers={'retry-after':'120'}) if model==M1 else text_response()
    transport(monkeypatch,handler)
    if status==429:
        with pytest.raises(router.OpenRouterUnavailable):router.gerar_texto_livre('test')
        with pytest.raises(router.OpenRouterUnavailable,match='cooldown'):router.gerar_texto_livre('test')
        assert calls==[M1]
    else:
        assert router.gerar_texto_livre('test')=='OK'
        assert calls==[M1,M2]

@pytest.mark.parametrize('model',["test/paid",'openrouter/auto','openrouter/free'])
def test_rejects_paid_auto_without_network(monkeypatch,model):
    transport(monkeypatch,lambda request:pytest.fail('network must not be called'))
    with pytest.raises(router.OpenRouterUnavailable,match='paid/non-free'):
        router._attempt(model,'test')

@pytest.mark.parametrize('price',['1','-1',None,'bad'])
def test_catalog_price_guard(monkeypatch,price):
    monkeypatch.setattr(router,'_catalog',[entry(M1,price=price)])
    transport(monkeypatch,lambda request:pytest.fail('paid model must not be called'))
    with pytest.raises(router.OpenRouterUnavailable,match='not verified'):
        router._attempt(M1,'test')

def test_json_invalid_then_next(monkeypatch):
    calls=[]
    def handler(request):
        calls.append(json.loads(request.content)['model'])
        return text_response('not json' if len(calls)==1 else '{"x":2}')
    transport(monkeypatch,handler)
    assert router.gerar_json_livre('test',Mini).x==2 and calls==[M1,M2]

def test_empty_then_next(monkeypatch):
    calls=[]
    def handler(request):
        calls.append(json.loads(request.content)['model'])
        return text_response('' if len(calls)==1 else 'OK')
    transport(monkeypatch,handler)
    assert router.gerar_texto_livre('test')=='OK' and calls==[M1,M2]

def test_catalog_refresh(monkeypatch):
    monkeypatch.setattr(router,'_catalog',None)
    calls=[]
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200,json={'data':[entry(M1)]}) if request.method=='GET' else text_response()
    transport(monkeypatch,handler)
    assert router.gerar_texto_livre('test')=='OK' and calls==['GET','POST']

def test_wall_timeout(monkeypatch):
    async def handler(request):
        await asyncio.sleep(1)
        return text_response()
    transport(monkeypatch,handler)
    monkeypatch.setattr(router,'_TIMEOUT_SECONDS',0.01)
    monkeypatch.setattr(router,'OPENROUTER_TEXT_MODELS',(M1,))
    with pytest.raises(router.OpenRouterUnavailable,match='timeout'):router.gerar_texto_livre('test')

def test_network_then_next(monkeypatch):
    calls=[]
    def handler(request):
        calls.append(json.loads(request.content)['model'])
        if len(calls)==1:raise httpx.ConnectError('network')
        return text_response()
    transport(monkeypatch,handler)
    assert router.gerar_texto_livre('test')=='OK' and calls==[M1,M2]

def png():
    out=io.BytesIO();Image.new('RGB',(8,8),'blue').save(out,'PNG');return out.getvalue()

def image_handler(request):
    if request.method=='GET':
        return httpx.Response(200,json={'endpoints':[{'provider_tag':'zero',
              'pricing':[{'billable':'output_image','cost_usd':0}]}]})
    payload=json.loads(request.content)
    assert payload['provider']=={'only':['zero'],'allow_fallbacks':False}
    return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(png()).decode()}]})

def test_image_app_path(monkeypatch,tmp_path):
    monkeypatch.setattr(router,'_catalog',[entry(M1,'image')])
    transport(monkeypatch,image_handler)
    monkeypatch.setattr(image_gen,'IMAGE_CHAIN',['openrouter','cloudflare'])
    monkeypatch.setattr(image_gen,'_try_cloudflare',lambda *a:pytest.fail('unexpected fallback'))
    result=image_gen.gerar_cena_com_provider('test','title','support',tmp_path/'out.png')
    assert result.provider=='openrouter' and result.path.read_bytes().startswith(b'\x89PNG')

def test_image_paid_endpoint_rejected(monkeypatch):
    monkeypatch.setattr(router,'_catalog',[entry(M1,'image')])
    def handler(request):
        assert request.method=='GET'
        return httpx.Response(200,json={'endpoints':[{'provider_tag':'paid',
             'pricing':[{'billable':'output_image','cost_usd':0.02}]}]})
    transport(monkeypatch,handler)
    with pytest.raises(router.OpenRouterUnavailable,match='zero-price'):router.gerar_png_openrouter('test')

def test_no_free_image_slot_next_provider(monkeypatch,tmp_path):
    monkeypatch.setattr(router,'OPENROUTER_IMAGE_MODELS',())
    monkeypatch.setattr(image_gen,'IMAGE_CHAIN',['openrouter','cloudflare'])
    transport(monkeypatch,lambda req:pytest.fail('empty image slot must make no request'))
    monkeypatch.setattr(image_gen,'_try_cloudflare',lambda prompt,destination:
        image_gen.CenaResult(image_gen._salvar(destination,png()),'cloudflare','mock'))
    result=image_gen.gerar_cena_com_provider('test','title','support',tmp_path/'out.png')
    assert result.provider=='cloudflare' and 'no verified free image' in result.detail

@pytest.mark.parametrize('data',[b'',b'html',b'{bad'])
def test_malformed_image_next_provider(monkeypatch,tmp_path,data):
    monkeypatch.setattr(router,'_catalog',[entry(M1,'image')])
    def handler(request):
        if request.method=='GET':return image_handler(request)
        return httpx.Response(200,content=data)
    transport(monkeypatch,handler)
    result=image_gen._try_openrouter('test',tmp_path/'bad.png')
    assert result.path is None and 'dummy-not-a-real-secret' not in result.detail

def test_429_moves_to_gemini_once(monkeypatch):
    calls=[]
    def handler(request):
        calls.append('openrouter');return httpx.Response(429)
    transport(monkeypatch,handler)
    monkeypatch.setattr(gemini_client,'_com_failover',lambda *a:calls.append('gemini_mock') or Mini(x=7))
    assert gemini_client.gerar_json('test',Mini).x==7
    assert calls==['openrouter','gemini_mock']

def test_preserves_gemini_sticky(monkeypatch):
    ia_sessao.lembrar_texto('gemini-flash-lite-latest')
    transport(monkeypatch,lambda req:pytest.fail('sticky Gemini must run first'))
    monkeypatch.setattr(gemini_client,'_com_failover',lambda *a:Mini(x=3))
    assert gemini_client.gerar_json('test',Mini).x==3
