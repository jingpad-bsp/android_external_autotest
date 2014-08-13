package autotest.moblab;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.SimpleCallback;
import autotest.common.ui.TabView;
import autotest.common.ui.NotifyManager;

import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.FileUpload;
import com.google.gwt.user.client.ui.FormPanel;
import com.google.gwt.user.client.ui.FormPanel.SubmitCompleteEvent;
import com.google.gwt.user.client.ui.FormPanel.SubmitCompleteHandler;
import com.google.gwt.user.client.ui.FormPanel.SubmitEvent;
import com.google.gwt.user.client.ui.FormPanel.SubmitHandler;


public class BotoKeyView extends TabView {
    private FileUpload botoKeyUpload;
    private Button submitButton;
    private FormPanel botoKeyUploadForm;

    @Override
    public String getElementId() {
        return "boto_key";
    }

    @Override
    public void initialize() {
        super.initialize();

        botoKeyUpload = new FileUpload();
        botoKeyUpload.setName("botokey");

        botoKeyUploadForm = new FormPanel();
        botoKeyUploadForm.setAction(JsonRpcProxy.AFE_BASE_URL + "upload/");
        botoKeyUploadForm.setEncoding(FormPanel.ENCODING_MULTIPART);
        botoKeyUploadForm.setMethod(FormPanel.METHOD_POST);
        botoKeyUploadForm.setWidget(botoKeyUpload);

        submitButton = new Button("Submit", new ClickHandler() {
            public void onClick(ClickEvent event) {
                botoKeyUploadForm.submit();
            }
        });

        botoKeyUploadForm.addSubmitCompleteHandler(new SubmitCompleteHandler() {
            public void onSubmitComplete(SubmitCompleteEvent event) {
                String fileName = event.getResults();
                JSONObject params = new JSONObject();
                params.put("boto_key", new JSONString(fileName));
                rpcCall(params);
            }
        });

        addWidget(botoKeyUploadForm, "view_boto_key");
        addWidget(submitButton, "view_submit_boto_key");
    }

    public void rpcCall(JSONObject params) {
        JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
        rpcProxy.rpcCall("set_boto_key", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                NotifyManager.getInstance().showMessage("Boto key uploaded.");
            }
        });
    }

}