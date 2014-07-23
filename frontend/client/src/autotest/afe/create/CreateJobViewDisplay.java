package autotest.afe.create;

import autotest.afe.CheckBoxPanel;
import autotest.afe.CheckBoxPanelDisplay;
import autotest.afe.ControlTypeSelect;
import autotest.afe.ControlTypeSelectDisplay;
import autotest.afe.HostSelector;
import autotest.afe.HostSelectorDisplay;
import autotest.afe.IButton;
import autotest.afe.IButton.ButtonImpl;
import autotest.afe.ICheckBox;
import autotest.afe.ICheckBox.CheckBoxImpl;
import autotest.afe.ITextArea;
import autotest.afe.ITextArea.TextAreaImpl;
import autotest.afe.ITextBox;
import autotest.afe.ITextBox.TextBoxImpl;
import autotest.afe.RadioChooser;
import autotest.afe.RadioChooserDisplay;
import autotest.afe.TestSelector;
import autotest.afe.TestSelectorDisplay;
import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.SimplifiedList;
import autotest.common.ui.ToolTip;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.logical.shared.HasCloseHandlers;
import com.google.gwt.event.logical.shared.HasOpenHandlers;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.DisclosurePanel;
import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HasValue;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;

public class CreateJobViewDisplay implements CreateJobViewPresenter.Display {
    public static final int CHECKBOX_PANEL_COLUMNS = 5;

    private TextBox jobName = new TextBox();
    private ToolTip jobNameToolTip = new ToolTip(
        "?",
        "Name for the job. The string should be meaningful when viewing a list of jobs.");
    private ExtendedListBox priorityList = new ExtendedListBox();
    private ToolTip priorityListToolTip = new ToolTip(
        "?",
        "Lowest to highest: Weekly, Daily, PostBuild, Default.");
    private TextBoxImpl kernel = new TextBoxImpl();
    private ToolTip kernelToolTip = new ToolTip(
        "?",
        "A URL pointing to a kernel source tarball or a .rpm or .deb package to " +
        "install on the test machine before testing. Leave blank to skip this step. " +
        "Example: \"2.6.18-rc3\" or \"http://example.com/kernel-2.6.30.rpm\". " +
        "Separate multiple kernels with a comma and/or space.");
    private TextBoxImpl kernel_cmdline = new TextBoxImpl();
    private TextBoxImpl image_url = new TextBoxImpl();
    private ToolTip image_urlToolTip = new ToolTip(
        "?",
        "Name of the test image to use. Example: \"x86-alex-release/R27-3837.0.0\". " +
        "If no image is specified, the latest ToT image is used.");
    private TextBox timeout = new TextBox();
    private ToolTip timeoutToolTip = new ToolTip(
        "?",
        "The number of minutes after the job creation before the scheduler " +
        "automatically aborts an incomplete job.");
    private TextBox maxRuntime = new TextBox();
    private ToolTip maxRuntimeToolTip = new ToolTip(
        "?",
        "The number of minutes after the job starts running before the scheduler " +
        "automatically aborts an incomplete job.");
    private TextBox testRetry = new TextBox();
    private ToolTip testRetryToolTip = new ToolTip(
        "?",
        "Number of times to retry test if the test did not complete successfully.");
    private TextBox emailList = new TextBox();
    private ToolTip emailListToolTip = new ToolTip(
        "?",
        "Email addresses to notify when this job completes. " +
        "Use a comma or space to separate multiple addresses.");
    private CheckBoxImpl skipVerify = new CheckBoxImpl();
    private ToolTip skipVerifyToolTip = new ToolTip(
        "?",
        "Skips the host verification step before running the job. " +
        "This is useful for machine reinstalls, for example.");
    private CheckBoxImpl skipReset = new CheckBoxImpl();
    private ToolTip skipResetToolTip = new ToolTip(
        "?",
        "Skips the host reset step before running the job.");
    private RadioChooserDisplay rebootBefore = new RadioChooserDisplay();
    private ToolTip rebootBeforeToolTip = new ToolTip(
        "?",
        "Reboots all assigned hosts before the job runs. " +
        "Click If dirty to reboot the host only if it hasn’t been rebooted " +
        "since it was added, locked, or after running the last job.");
    private RadioChooserDisplay rebootAfter = new RadioChooserDisplay();
    private ToolTip rebootAfterToolTip = new ToolTip(
        "?",
        "Reboots all assigned hosts after the job runs. Click If all tests passed " +
        "to skip rebooting the host if any test in the job fails.");
    private CheckBox parseFailedRepair = new CheckBox();
    private ToolTip parseFailedRepairToolTip = new ToolTip(
        "?",
        "When a host fails repair, displays repair and verify test entries in " +
        "the results database along with a SERVER_JOB entry. " +
        "Otherwise, no information is displayed in TKO (Result Database).");
    private CheckBoxImpl hostless = new CheckBoxImpl();
    private ToolTip hostlessToolTip = new ToolTip(
        "?",
        "Check to run a suite of tests, and select Server from the Test type dropdown list.");
    private TextBox pool = new TextBox();
    private ToolTip poolToolTip = new ToolTip(
        "?",
        "Specify the pool of machines to use for suite job.");
    private TextBoxImpl args = new TextBoxImpl();
    private ToolTip argsToolTip = new ToolTip(
        "?",
        "Example: \"device_addrs=00:1F:20:33:6A:1E, arg2=value2, arg3=value3\". " +
        "Separate multiple args with commas.");
    private TestSelectorDisplay testSelector = new TestSelectorDisplay();
    private CheckBoxPanelDisplay profilersPanel = new CheckBoxPanelDisplay(CHECKBOX_PANEL_COLUMNS);
    private CheckBoxImpl runNonProfiledIteration =
        new CheckBoxImpl("Run each test without profilers first");
    private ExtendedListBox droneSet = new ExtendedListBox();
    private TextAreaImpl controlFile = new TextAreaImpl();
    private DisclosurePanel controlFilePanel = new DisclosurePanel("");
    private ControlTypeSelectDisplay controlTypeSelect = new ControlTypeSelectDisplay();
    private TextBoxImpl synchCountInput = new TextBoxImpl();
    private ButtonImpl editControlButton = new ButtonImpl();
    private HostSelectorDisplay hostSelector = new HostSelectorDisplay();
    private ButtonImpl submitJobButton = new ButtonImpl("Submit Job");
    private Button createTemplateJobButton = new Button("Create Template Job");
    private Button resetButton = new Button("Reset");
    private Label viewLink = new Label("");

    public void initialize(HTMLPanel panel) {
        Panel profilerControls = new VerticalPanel();
        profilerControls.add(profilersPanel);
        profilerControls.add(runNonProfiledIteration);

        controlFile.setSize("50em", "30em");

        HorizontalPanel controlOptionsPanel = new HorizontalPanel();
        controlOptionsPanel.setVerticalAlignment(HorizontalPanel.ALIGN_BOTTOM);
        controlOptionsPanel.add(controlTypeSelect);
        Label useLabel = new Label("Use");
        useLabel.getElement().getStyle().setProperty("marginLeft", "1em");
        synchCountInput.setSize("3em", ""); // set width only
        synchCountInput.getElement().getStyle().setProperty("margin", "0 0.5em 0 0.5em");
        controlOptionsPanel.add(useLabel);
        controlOptionsPanel.add(synchCountInput);
        controlOptionsPanel.add(new Label("host(s) per execution"));
        Panel controlEditPanel = new VerticalPanel();
        controlEditPanel.add(controlOptionsPanel);
        controlEditPanel.add(controlFile);

        Panel controlHeaderPanel = new HorizontalPanel();
        controlHeaderPanel.add(controlFilePanel.getHeader());
        controlHeaderPanel.add(viewLink);
        controlHeaderPanel.add(editControlButton);

        controlFilePanel.setHeader(controlHeaderPanel);
        controlFilePanel.add(controlEditPanel);

        panel.add(jobName, "create_job_name");
        panel.add(jobNameToolTip, "create_job_name");
        panel.add(kernel, "create_kernel");
        panel.add(kernelToolTip, "create_kernel");
        panel.add(kernel_cmdline, "create_kernel_cmdline");
        panel.add(image_url, "create_image_url");
        panel.add(image_urlToolTip, "create_image_url");
        panel.add(timeout, "create_timeout");
        panel.add(timeoutToolTip, "create_timeout");
        panel.add(maxRuntime, "create_max_runtime");
        panel.add(maxRuntimeToolTip, "create_max_runtime");
        panel.add(testRetry, "create_test_retry");
        panel.add(testRetryToolTip, "create_test_retry");
        panel.add(emailList, "create_email_list");
        panel.add(emailListToolTip, "create_email_list");
        panel.add(priorityList, "create_priority");
        panel.add(priorityListToolTip, "create_priority");
        panel.add(skipVerify, "create_skip_verify");
        panel.add(skipVerifyToolTip, "create_skip_verify");
        panel.add(skipReset, "create_skip_reset");
        panel.add(skipResetToolTip, "create_skip_reset");
        panel.add(rebootBefore, "create_reboot_before");
        panel.add(rebootBeforeToolTip, "create_reboot_before");
        panel.add(rebootAfter, "create_reboot_after");
        panel.add(rebootAfterToolTip, "create_reboot_after");
        panel.add(parseFailedRepair, "create_parse_failed_repair");
        panel.add(parseFailedRepairToolTip, "create_parse_failed_repair");
        panel.add(hostless, "create_hostless");
        panel.add(hostlessToolTip, "create_hostless");
        panel.add(pool, "create_pool");
        panel.add(poolToolTip, "create_pool");
        panel.add(args, "create_args");
        panel.add(argsToolTip, "create_args");
        panel.add(testSelector, "create_tests");
        panel.add(profilerControls, "create_profilers");
        panel.add(controlFilePanel, "create_edit_control");
        panel.add(hostSelector, "create_host_selector");
        panel.add(submitJobButton, "create_submit");
        panel.add(createTemplateJobButton, "create_template_job");
        panel.add(resetButton, "create_reset");
        panel.add(droneSet, "create_drone_set");
    }

    public CheckBoxPanel.Display getCheckBoxPanelDisplay() {
        return profilersPanel;
    }

    public ControlTypeSelect.Display getControlTypeSelectDisplay() {
        return controlTypeSelect;
    }

    public ITextArea getControlFile() {
        return controlFile;
    }

    public HasCloseHandlers<DisclosurePanel> getControlFilePanelClose() {
        return controlFilePanel;
    }

    public HasOpenHandlers<DisclosurePanel> getControlFilePanelOpen() {
        return controlFilePanel;
    }

    public HasClickHandlers getCreateTemplateJobButton() {
        return createTemplateJobButton;
    }

    public SimplifiedList getDroneSet() {
        return droneSet;
    }

    public IButton getEditControlButton() {
        return editControlButton;
    }

    public HasText getEmailList() {
        return emailList;
    }

    public HostSelector.Display getHostSelectorDisplay() {
        return hostSelector;
    }

    public ICheckBox getHostless() {
        return hostless;
    }

    public HasText getPool() {
        return pool;
    }

    public ITextBox getArgs() {
        return args;
    }

    public HasText getJobName() {
        return jobName;
    }

    public ITextBox getKernel() {
        return kernel;
    }

    public ITextBox getKernelCmdline() {
        return kernel_cmdline;
    }

    public ITextBox getImageUrl() {
        return image_url;
    }

    public HasText getMaxRuntime() {
        return maxRuntime;
    }

    public HasText getTestRetry() {
        return testRetry;
    }

    public HasValue<Boolean> getParseFailedRepair() {
        return parseFailedRepair;
    }

    public ExtendedListBox getPriorityList() {
        return priorityList;
    }

    public RadioChooser.Display getRebootAfter() {
        return rebootAfter;
    }

    public RadioChooser.Display getRebootBefore() {
        return rebootBefore;
    }

    public HasClickHandlers getResetButton() {
        return resetButton;
    }

    public ICheckBox getRunNonProfiledIteration() {
        return runNonProfiledIteration;
    }

    public ICheckBox getSkipVerify() {
        return skipVerify;
    }

    public ICheckBox getSkipReset() {
      return skipReset;
    }

    public IButton getSubmitJobButton() {
        return submitJobButton;
    }

    public ITextBox getSynchCountInput() {
        return synchCountInput;
    }

    public TestSelector.Display getTestSelectorDisplay() {
        return testSelector;
    }

    public HasText getTimeout() {
        return timeout;
    }

    public HasText getViewLink() {
        return viewLink;
    }

    public void setControlFilePanelOpen(boolean isOpen) {
        controlFilePanel.setOpen(isOpen);
    }
}
