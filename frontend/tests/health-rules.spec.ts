import { expect, test } from '@playwright/test';

test('规则草稿批准后评估设备，停用后未评估并保留来源', async ({ page, baseURL }) => {
  test.setTimeout(90000);
  page.setDefaultTimeout(10000);
  const login=await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}});
  const headers={Origin:new URL(baseURL!).origin,'X-CSRF-Token':(await login.json()).csrf_token};
  const name='隔离健康规则-'+Date.now();
  const methodResponse=await page.request.post('/api/laboratory/configuration/methods',{headers,data:{test_type:'MOISTURE',display_name:name,version_label:name,fields:[{code:'MOISTURE',display_name:'微水',unit_code:'TEST-UNIT'}]}});
  expect(methodResponse.status()).toBe(201);
  const method=(await methodResponse.json()).id;
  const asset='40000000-0000-0000-0000-000000000002';
  const response=await page.request.post('/api/laboratory/samples',{headers,data:{sampled_at:new Date(Date.now()-60000).toISOString(),received_at:new Date().toISOString(),site_name:'test',equipment_serial:'test',container_count:1,identity_status:'ASSOCIATED',formal_asset_id:asset}});
  expect(response.status()).toBe(201);
  const barcode=(await response.json()).barcode_value;
  expect((await page.request.post(`/api/laboratory/samples/${barcode}/tests`,{headers,data:{test_type:'MOISTURE',method_version_id:method,measured_at:new Date().toISOString(),result:{kind:'MOISTURE',result:{qualifier:'EQ',value:'20'}}}})).status()).toBe(201);
  expect((await page.request.post(`/api/laboratory/samples/${barcode}/finalization`,{headers,data:{acknowledged_warning_codes:[]}})).status()).toBe(200);
  await page.goto('/assets/analysis/rules');
  await page.getByLabel('规则名称',{exact:true}).fill(name);
  await page.getByLabel('适用方法版本',{exact:true}).selectOption(method);
  await page.getByLabel('比较阈值',{exact:true}).fill('10');
  await page.getByLabel('生效时间',{exact:true}).fill('2026-01-01T00:00');
  for(const width of [1920,1280]){
    await page.setViewportSize({width,height:1080});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    const boxes=await page.locator('.health-form input,.health-form select').evaluateAll(elements=>elements.map(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};}));
    for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
      const a=boxes[i],b=boxes[j];expect(a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top).toBeTruthy();
    }
  }
  await page.screenshot({path:'/app/test-results/health-rules-desktop.png',fullPage:true});
  await page.getByRole('button',{name:'保存草稿',exact:true}).click();
  const row=page.getByRole('table',{name:'健康规则列表'}).getByRole('row').filter({hasText:name});
  await expect(row).toContainText('草稿');
  await row.getByRole('button',{name:'批准启用',exact:true}).click();
  await page.getByLabel('审批或停用原因').fill('仅隔离测试');
  await page.getByRole('button',{name:'确认批准启用',exact:true}).click();
  await expect(row).toContainText('已启用');
  await page.goto(`/assets/equipment/${asset}`);
  const panel=page.getByRole('region',{name:'设备健康评估'});
  await expect(panel).toContainText('警示');
  await expect(panel.locator('.health-status')).toHaveCSS('color','rgb(187, 37, 54)');
  await panel.getByText('查看评估来源',{exact:true}).click();
  await expect(panel).toContainText(barcode);
  await expect(panel).toContainText('TEST-UNIT');
  await expect(panel.getByRole('link',{name:'条码报告'})).toHaveAttribute('href',`/lab/reports?barcode=${barcode}`);
  await page.goto('/assets/equipment/30000000-0000-0000-0000-000000000001');
  await expect(panel).toContainText('子设备汇总：警示');
  await panel.getByText('查看评估来源',{exact:true}).click();
  await expect(panel).toContainText('TX-CURRENT-2002');
  await expect(panel).toContainText(barcode);
  for(const width of [1920,1280]){
    await page.setViewportSize({width,height:1080});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  }
  await page.goto('/assets/analysis/rules');
  await row.getByRole('button',{name:'停用',exact:true}).click();
  await page.getByLabel('审批或停用原因').fill('测试结束');
  await page.getByRole('button',{name:'确认停用',exact:true}).click();
  await expect(row).toContainText('已停用');
  await page.goto(`/assets/equipment/${asset}`);
  await expect(panel).toContainText('未评估');
  await page.screenshot({path:'/app/test-results/health-desktop.png',fullPage:true});
});

test('编辑保留精确时间阈值，等待提交时锁定字段，冲突不清空输入',async({page,baseURL})=>{
  page.setDefaultTimeout(10000);
  const login=await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},data:{username:'browser-admin',password:'Browser changed passphrase 84!'}});
  const headers={Origin:new URL(baseURL!).origin,'X-CSRF-Token':(await login.json()).csrf_token};
  const catalog=await(await page.request.get('/api/condition-analysis/rule-methods')).json();
  const method=catalog.find((m:{configured:boolean;test_type:string})=>m.configured&&m.test_type==='MOISTURE');
  const from='2026-11-01T07:30:12.345000Z';
  const payload={name:'精度回归-'+Date.now(),test_type:'MOISTURE',analyte:'MOISTURE',method_version_id:method.id,unit:'TEST-UNIT',priority:0,effective_from:from,operator:'GT',threshold:'999999999999.123456',severity:'WARNING'};
  const response=await page.request.post('/api/condition-analysis/rules',{headers,data:payload});
  expect(response.status()).toBe(201);const rule=await response.json();
  await page.goto('/assets/analysis/rules');
  await page.getByRole('row').filter({hasText:payload.name}).getByRole('button',{name:'编辑草稿'}).click();
  await page.getByLabel('规则名称',{exact:true}).fill(payload.name+'修改');
  let release=()=>{};const held=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/api/condition-analysis/rules/'+rule.id,async route=>{const result=await route.fetch();await held;await route.fulfill({response:result});});
  await page.getByRole('button',{name:'保存草稿',exact:true}).click();
  await expect(page.getByLabel('规则名称',{exact:true})).toBeDisabled();
  release();await expect(page.getByRole('status').filter({hasText:'草稿已保存'})).toBeVisible();
  const saved=(await(await page.request.get('/api/condition-analysis/rules')).json()).find((r:{id:string})=>r.id===rule.id);
  expect(new Date(saved.effective_from).getTime()).toBe(new Date(from).getTime());
  expect(saved.threshold).toBe(payload.threshold);
  await page.unroute('**/api/condition-analysis/rules/'+rule.id);
  await page.getByRole('row').filter({hasText:payload.name+'修改'}).getByRole('button',{name:'编辑草稿'}).click();
  await page.getByLabel('规则名称',{exact:true}).fill('保留我的输入');
  await page.route('**/api/condition-analysis/rules/'+rule.id,route=>route.fulfill({status:409,json:{code:'rule_revision_conflict'}}));
  await page.getByRole('button',{name:'保存草稿',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('规则已被其他操作更新');
  await expect(page.getByLabel('规则名称',{exact:true})).toHaveValue('保留我的输入');
});

test('只读账号无规则写入入口，健康加载失败不显示旧成功状态',async({page,baseURL})=>{
  await page.request.post('/api/auth/login',{headers:{Origin:new URL(baseURL!).origin},data:{username:'field-user',password:'Browser changed passphrase 84!'}});
  await page.goto('/assets/analysis/rules');
  await expect(page.getByRole('table',{name:'健康规则列表'})).toBeVisible();
  await expect(page.getByRole('button',{name:'保存草稿'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'批准启用',exact:true})).toHaveCount(0);
  await page.goto('/assets/equipment/40000000-0000-0000-0000-000000000002');
  const panel=page.getByRole('region',{name:'设备健康评估'});
  await expect(panel).toContainText('未评估');
  await page.route('**/api/condition-analysis/health/**',route=>route.fulfill({status:503,json:{code:'health_source_unavailable'}}));
  await panel.getByRole('button',{name:'刷新健康状态'}).click();
  await expect(panel.getByRole('alert')).toBeVisible();
  await expect(panel.locator('.health-status')).toHaveCount(0);
});
