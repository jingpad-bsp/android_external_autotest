package autotest.moblab.wizard;

import com.google.gwt.event.logical.shared.ValueChangeEvent;
import com.google.gwt.event.logical.shared.ValueChangeHandler;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.TextBox;

import autotest.common.Utils;
import autotest.moblab.rpc.CloudStorageInfo;
import autotest.moblab.rpc.MoblabRpcCallbacks;
import autotest.moblab.rpc.MoblabRpcHelper;
import autotest.moblab.rpc.OperationStatus;
import autotest.common.ui.ToolTip;

import java.util.HashMap;

/**
 * Wizard card for cloud storage configuration.
 */
public class CloudStorageCard extends FlexWizardCard {
  /**
   * The cached cloud storage information.
   */
  private CloudStorageInfo cloudStorageInfo;

  /**
   * Checkbox for if reuse existing boto file.
   */
  private CheckBox chkUseExisting;

  public CloudStorageCard() {
    super();
    setViewTitle("Google Cloud Storage Configuration");
    setEditTitle("Configure Access to Google Cloud Storage");
  }

  @Override
  protected void updateModeUI() {
    if (cloudStorageInfo != null) {
      resetUI();
      int row = 0;
      // In edit mode, display the check box for re-using existing boto file.
      if (ConfigWizard.Mode.Edit == getMode()) {
        chkUseExisting = new CheckBox("Use Existing Boto File on Moblab Device.");
        layoutTable.setWidget(row, 1, chkUseExisting);
        chkUseExisting.addValueChangeHandler(new ValueChangeHandler<Boolean>() {
          @Override
          public void onValueChange(ValueChangeEvent<Boolean> event) {
            if (cloudStorageInfo != null) {
              cloudStorageInfo.setUseExistingBotoFile(event.getValue());
            }
            TextBox box = getValueFieldEditor(CloudStorageInfo.JSON_FIELD_BOTO_KEY_ID);
            if (box != null) {
              box.setEnabled(!event.getValue());
            }
            box = getValueFieldEditor(CloudStorageInfo.JSON_FIELD_BOTO_SECRET_KEY);
            if (box != null) {
              box.setEnabled(!event.getValue());
            }
          }
        });
      }

      // Row for boto key id.
      row++;
      layoutTable.setWidget(row, 0, new Label("Boto Key ID"));
      layoutTable.setWidget(row, 1, createValueFieldWidget(CloudStorageInfo.JSON_FIELD_BOTO_KEY_ID,
          cloudStorageInfo.getBotoKey()));

      // Row for boto key secret.
      row++;
      layoutTable.setWidget(row, 0, new Label("Boto Key Secrete"));
      layoutTable.setWidget(row, 1, createStringValueFieldWidget(
          CloudStorageInfo.JSON_FIELD_BOTO_SECRET_KEY, cloudStorageInfo.getBotoSecret(), true));

      // Row for image storage bucket url.
      row++;
      layoutTable.setWidget(row, 0, new Label("Image Storage Bucket URL"));
      String url = cloudStorageInfo.getImageStorageServer();
      layoutTable.setWidget(row, 1,
          createValueFieldWidget(CloudStorageInfo.JSON_FIELD_IMAGE_STORAGE_URL, url));
      if (url != null && ConfigWizard.Mode.View == getMode()) {
        Anchor link = Utils.createGoogleStorageHttpUrlLink("link", url);
        layoutTable.setWidget(row, 2, link);
      }

      // Row for result bucket url.
      row++;
      layoutTable.setWidget(row, 0, new Label("Result Bucket URL(optional)"));
      url = cloudStorageInfo.getResultStorageServer();
      layoutTable.setWidget(row, 1,
          createValueFieldWidget(CloudStorageInfo.JSON_FIELD_RESULT_STORAGE_URL, url));
      if (url != null && ConfigWizard.Mode.View == getMode()) {
        Anchor link = Utils.createGoogleStorageHttpUrlLink("link", url);
        layoutTable.setWidget(row, 2, link);
      } else if (ConfigWizard.Mode.Edit == getMode()){
        ToolTip tip = new ToolTip( "?",
          "If not specicifed, Molab will use the image bucket for result uploading.");
        layoutTable.setWidget(row, 2, tip);
      }

      if (ConfigWizard.Mode.Edit == getMode()) {
        chkUseExisting.setValue(cloudStorageInfo.isUseExistingBotoFile(), true);
      }
    } else {
      MoblabRpcHelper.fetchCloudStorageInfo(new MoblabRpcCallbacks.FetchCloudStorageInfoCallback() {
        @Override
        public void onCloudStorageInfoFetched(CloudStorageInfo info) {
          cloudStorageInfo = info;
          updateModeUI();
        }
      });
    }
  }

  @Override
  public void validate(final CardValidationCallback callback) {
    // If not use existing boto, than boto id and boto secret fields can not be empty.
    if (!chkUseExisting.getValue()) {
      cloudStorageInfo
          .setBotoKey(getStringValueFieldValue(CloudStorageInfo.JSON_FIELD_BOTO_KEY_ID));
      cloudStorageInfo
          .setBotoSecret(getStringValueFieldValue(CloudStorageInfo.JSON_FIELD_BOTO_SECRET_KEY));
      if (cloudStorageInfo.getBotoKey() == null || cloudStorageInfo.getBotoSecret() == null) {
        callback.onValidationStatus(
            new OperationStatus(false, "The boto key fields could not be empty"));
        return;
      }
    }

    cloudStorageInfo.setImageStorageServer(
        getStringValueFieldValue(CloudStorageInfo.JSON_FIELD_IMAGE_STORAGE_URL));
    cloudStorageInfo.setResultStorageServer(
        getStringValueFieldValue(CloudStorageInfo.JSON_FIELD_RESULT_STORAGE_URL));
    // Image bucket and result bucket can not be empty.
    if (cloudStorageInfo.getImageStorageServer() == null) {
      callback.onValidationStatus(
          new OperationStatus(false, "The image bucket URL fields could not be empty"));
      return;
    }

    // Sends validation request to server to validate the boto key and bucket urls.
    MoblabRpcHelper.validateCloudStorageInfo(cloudStorageInfo,
        new MoblabRpcCallbacks.ValidateCloudStorageInfoCallback() {
          @Override
          public void onCloudStorageInfoValidated(OperationStatus status) {
            if (!status.isOk()) {
              callback.onValidationStatus(status);
              return;
            }
            CloudStorageCard.super.validate(callback);
          }
        });
    return;
  }

  /**
   * Gets the string input field value.
   */
  protected String getStringValueFieldValue(String fieldId) {
    TextBox textBox = getValueFieldEditor(fieldId);
    String value = textBox.getValue();
    if (value != null) {
      value = value.trim();
    }

    if (value == null || value.length() == 0) {
      return null;
    }
    return value;
  }

  @Override
  public void resetData() {
    cloudStorageInfo = null;
    super.resetData();
  }

  @Override
  public void collectConfigData(@SuppressWarnings("unused") HashMap<String, JSONObject> map) {
    if (map != null && cloudStorageInfo != null) {
      map.put(MoblabRpcHelper.RPC_PARAM_CLOUD_STORAGE_INFO, cloudStorageInfo.toJson());
    }
  }
}
