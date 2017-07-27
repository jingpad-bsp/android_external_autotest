package autotest.moblab.rpc;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

/**
 * Wifi configuration RPC entity.
 */
public class WifiInfo extends JsonRpcEntity {
  public static final String JSON_FIELD_AP_NAME = "wifi_dut_ap_name";
  public static final String JSON_FIELD_AP_PASS = "wifi_dut_ap_pass";

  /**
   * The wifi AP name to connect to.
   */
  private String apName;

  /**
   * The wifi AP password to use.
   */
  private String apPass;

  public WifiInfo() {
    reset();
  }

  public String getApName() {
    return apName;
  }

  public String getApPass() {
    return apPass;
  }

  public void setApName(String apName) {
    this.apName = apName.trim();
  }

  public void setApPass(String apPass) {
    this.apPass = apPass.trim();
  }

  private void reset() {
    apName = null;
    apPass = null;
  }

  @Override
  public void fromJson(JSONObject object) {
    if (object != null) {
      apName = getStringFieldOrDefault(object, JSON_FIELD_AP_NAME, null);
      apPass = getStringFieldOrDefault(object, JSON_FIELD_AP_PASS, null);
    }
  }

  @Override
  public JSONObject toJson() {
    JSONObject object = new JSONObject();
    object.put(JSON_FIELD_AP_NAME, new JSONString("Test"));
    if (apName != null) {
      object.put(JSON_FIELD_AP_NAME, new JSONString(apName));
    }
    object.put(JSON_FIELD_AP_PASS, new JSONString("Pass"));
    if (apPass != null) {
      object.put(JSON_FIELD_AP_PASS, new JSONString(apPass));
    }
    return object;
  }
}
