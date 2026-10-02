import { expect, test, type Page } from '@playwright/test';

async function prepare(page:Page,baseURL:string){
  page.setDefaultTimeout(10000);
  const login=await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}});
  const headers={Origin:new URL(baseURL!).origin,'X-CSRF-Token':(await login.json()).csrf_token};
  const name='隔离报警-'+Date.now(),asset='30000000-0000-0000-0000-000000000015';
  const method=await(await page.request.post('/api/laboratory/configuration/methods',{headers,data:{test_type:'MOISTURE',display_name:name,version_label:name,fields:[{code:'MOISTURE',display_name:'微水',unit_code:'TEST-UNIT'}]}})).json();
  const rule=await(await page.request.post('/api/condition-analysis/rules',{headers,data:{name,test_type:'MOISTURE',analyte:'MOISTURE',method_version_id:method.id,unit:'TEST-UNIT',priority:10,effective_from:'2026-01-01T00:00:00Z',operator:'GT',threshold:'10',severity:'WARNING'}})).json();
  expect((await page.request.post(`/api/condition-analysis/rules/${rule.id}/activate`,{headers,data:{expected_revision:0,reason:'isolated test only'}})).status()).toBe(200);
  async function sample(value:string,methodId=method.id){
    const result=await page.request.post('/api/laboratory/samples',{headers,data:{sampled_at:new Date(Date.now()-1).toISOString(),received_at:new Date().toISOString(),site_name:'test',equipment_serial:'test',container_count:1,identity_status:'ASSOCIATED',formal_asset_id:asset}});
    expect(result.status()).toBe(201);
    const barcode=(await result.json()).barcode_value;
    expect((await page.request.post(`/api/laboratory/samples/${barcode}/tests`,{headers,data:{test_type:'MOISTURE',method_version_id:methodId,measured_at:new Date().toISOString(),result:{kind:'MOISTURE',result:{qualifier:'EQ',value}}}})).status()).toBe(201);
    expect((await page.request.post(`/api/laboratory/samples/${barcode}/finalization`,{headers,data:{acknowledged_warning_codes:[]}})).status()).toBe(200);
    return barcode;
  }
  // Repeated local runs retain data. Close only this isolated fixture's prior
  // episode through the public lifecycle, not via direct database mutation.
  const previous=await(await page.request.get('/api/condition-analysis/alarms?asset_id='+asset)).json();
  for(const alarm of previous.items){
    await sample('2',alarm.latest_abnormal[0].measurement.method_version_id);
    expect((await(await page.request.get('/api/condition-analysis/alarms?asset_id='+asset)).json()).unresolved_count).toBe(0);
  }
  const abnormal=await sample('20');
  return {asset,headers,sample,abnormal};
}

test('报警入口、确认、兼容正常结果解除与历史追溯',async({page,baseURL})=>{
  test.setTimeout(90000);
  const {asset,sample,abnormal}=await prepare(page,baseURL!);
  await page.goto(`/assets/equipment/${asset}`);
  await page.getByRole('link',{name:'未解除报警 1 条'}).click();
  const table=page.getByRole('table',{name:'报警列表'});
  await expect(table).toContainText('待确认');
  await table.getByRole('link',{name:'查看报警'}).click();
  await expect(page.getByRole('region',{name:'报警详情'})).toContainText(abnormal);
  await page.getByLabel('确认说明').fill('已查看，等待后续检测');
  await page.getByRole('button',{name:'确认报警',exact:true}).click();
  await expect(page.getByRole('region',{name:'报警详情'})).toContainText('已确认');
  await expect(page.getByRole('region',{name:'报警详情'})).toContainText('警示');
  const normal=await sample('2');
  await page.getByRole('button',{name:'刷新报警详情'}).click();
  const detail=page.getByRole('region',{name:'报警详情'});
  await expect(detail).toContainText('已解除');
  await expect(detail).toContainText(normal);
  await expect(detail.getByRole('link',{name:'条码报告'}).first()).toHaveAttribute('href',`/lab/reports?barcode=${abnormal}`);
  for(const width of [1920,1280]){
    await page.setViewportSize({width,height:1080});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  }
  await page.screenshot({path:'/app/test-results/alarm-detail.png',fullPage:true});
  await page.getByRole('link',{name:'返回报警列表'}).click();
  await page.getByLabel('报警范围').selectOption('history');
  await page.getByRole('button',{name:'筛选报警',exact:true}).click();
  await expect(table).toContainText('已解除');
});

test('只读权限、确认冲突保留说明和读取失败不显示旧计数',async({page,baseURL})=>{
  page.setDefaultTimeout(10000);
  const origin=new URL(baseURL!).origin;
  const {asset}=await prepare(page,baseURL!);
  const current=await(await page.request.get('/api/condition-analysis/alarms?asset_id='+asset)).json();
  const alarm=current.items[0];
  await page.request.post('/api/auth/login',{headers:{Origin:origin},data:{username:'operations-reader',password:'Browser changed passphrase 84!'}});
  await page.goto('/assets/analysis/alarms?alarm='+alarm.id);
  await expect(page.getByRole('region',{name:'报警详情'})).toContainText('待确认');
  await expect(page.getByRole('button',{name:'确认报警',exact:true})).toHaveCount(0);
  await expect(page.getByRole('link',{name:'检测记录',exact:true})).toHaveCount(0);
  await expect(page.getByRole('link',{name:'条码报告',exact:true}).first()).toBeVisible();
  await page.request.post('/api/auth/login',{headers:{Origin:origin},data:{username:'field-user',password:'Browser changed passphrase 84!'}});
  await page.reload();
  await page.getByLabel('确认说明').fill('保留现场检查说明');
  await page.route('**/alarms/*/acknowledgement',route=>route.fulfill({status:409,json:{code:'alarm_revision_conflict'}}));
  await page.getByRole('button',{name:'确认报警',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('报警已更新');
  await expect(page.getByLabel('确认说明')).toHaveValue('保留现场检查说明');
  await page.unroute('**/alarms/*/acknowledgement');
  await page.getByRole('button',{name:'刷新报警详情'}).click();
  await page.getByRole('button',{name:'确认报警',exact:true}).click();
  await expect(page.getByRole('region',{name:'报警详情'})).toContainText('现场工程师');
  await page.goto('/assets/analysis/alarms?asset_id='+asset);
  await expect(page.getByRole('table',{name:'报警列表'})).toContainText('已确认');
  for(const width of [1920,1280]){
    await page.setViewportSize({width,height:1080});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  }
  await page.screenshot({path:'/app/test-results/alarm-list.png',fullPage:true});
  await page.route('**/api/condition-analysis/alarms?*',route=>route.fulfill({status:503,json:{code:'alarm_source_unavailable'}}));
  await page.getByRole('button',{name:'刷新报警列表'}).click();
  await expect(page.getByRole('alert')).toContainText('报警服务暂不可用');
  await expect(page.getByRole('table',{name:'报警列表'})).toHaveCount(0);
});
