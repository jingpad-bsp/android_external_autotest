package autotest.moblab;

import autotest.common.ui.TabView;
import autotest.moblab.rpc.MoblabRpcCallbacks;
import autotest.moblab.rpc.MoblabRpcCallbacks.RunSuiteCallback;
import autotest.moblab.rpc.MoblabRpcHelper;
import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.HasVerticalAlignment;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.SimplePanel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;
import java.util.Arrays;
import java.util.List;


/**
 * Implement a tab to make a very easy way to run the most common moblab suites.
 */
public class SuiteRunnerView extends TabView {

  private VerticalPanel suiteRunnerMainPanel;
  private ListBox boardSelector;
  private ListBox buildSelector;
  private ListBox suiteSelector;
  private ListBox poolSelector;
  private Button actionButton;

  private static List<String> suiteNames = Arrays.asList("bvt-cq", "bvt-inline",
      "bvt-inline", "cts", "gts", "hardware_storagequal", "hardware_memoryqual");

  @Override
  public String getElementId() {
    return "suite_run";
  }

  @Override
  public void refresh() {
    super.refresh();
    boardSelector.clear();
    buildSelector.clear();
    suiteSelector.clear();
    poolSelector.clear();

    buildSelector.addItem("Select the build");
    suiteSelector.addItem("Select the suite");
    poolSelector.addItem("Select the pool");

    for (String suite : suiteNames) {
      suiteSelector.addItem(suite);
    }

    loadBoards();
    loadPools();
    addWidget(suiteRunnerMainPanel, "view_suite_run");
  };

  @Override
  public void initialize() {
    super.initialize();

    boardSelector = new ListBox();
    buildSelector = new ListBox();
    suiteSelector = new ListBox();
    poolSelector = new ListBox();

    boardSelector.addChangeHandler(new ChangeHandler() {
      @Override
      public void onChange(ChangeEvent event) {
        boardSelected();
      }
    });
    boardSelector.setStyleName("run_suite_selector");

    buildSelector.setEnabled(false);
    buildSelector.addChangeHandler(new ChangeHandler() {
      @Override
      public void onChange(ChangeEvent event) {
         buildSelected();
      }
    });
    buildSelector.setStyleName("run_suite_selector");

    suiteSelector.setEnabled(false);
    suiteSelector.addChangeHandler(new ChangeHandler() {
      @Override
      public void onChange(ChangeEvent event) {
        suiteSelected();
      }
    });
    suiteSelector.setStyleName("run_suite_selector");

    poolSelector.setEnabled(false);
    poolSelector.setStyleName("run_suite_selector");

    HorizontalPanel firstLine = createHorizontalLineItem("Select board:", boardSelector);
    HorizontalPanel secondLine = createHorizontalLineItem("Select build:", buildSelector);
    HorizontalPanel thirdLine = createHorizontalLineItem("Select suite:", suiteSelector);
    HorizontalPanel fourthLine = createHorizontalLineItem("Pool (Optional):", poolSelector);

    actionButton = new Button("Run Suite", new ClickHandler() {
      public void onClick(ClickEvent event) {
        int boardSelection = boardSelector.getSelectedIndex();
        int buildSelection = buildSelector.getSelectedIndex();
        int suiteSelection = suiteSelector.getSelectedIndex();
        int poolSelection = poolSelector.getSelectedIndex();
        if (boardSelection != 0 && buildSelection != 0 && suiteSelection != 0) {
	  String poolLabel = new String();
	  if (poolSelection != 0) {
	    poolLabel = poolSelector.getItemText(poolSelection);
	  }
          runSuite(boardSelector.getItemText(boardSelection),
              buildSelector.getItemText(buildSelection),
              suiteSelector.getItemText(suiteSelection),
              poolLabel);
        } else {
          Window.alert("You have to select a valid board, build and suite.");
        }
      }});

    actionButton.setEnabled(false);
    actionButton.setStyleName("run_suite_button");
    HorizontalPanel fifthLine = createHorizontalLineItem("", actionButton);

    suiteRunnerMainPanel = new VerticalPanel();

    suiteRunnerMainPanel.add(firstLine);
    suiteRunnerMainPanel.add(secondLine);
    suiteRunnerMainPanel.add(thirdLine);
    suiteRunnerMainPanel.add(fourthLine);
    suiteRunnerMainPanel.add(fifthLine);
  }

  private HorizontalPanel createHorizontalLineItem(String label, Widget item) {
    HorizontalPanel panel = new HorizontalPanel();
    panel.add(contstructLabel(label));
    panel.add(item);
    return panel;
  }

  private Label contstructLabel(String labelName) {
    Label label = new Label(labelName);
    label.setStyleName("run_suite_label");
    return label;
  }

  private void suiteSelected() {
    int selectedIndex = suiteSelector.getSelectedIndex();
    if (selectedIndex != 0) {
      actionButton.setEnabled(true);
    }
  }

  private void buildSelected() {
    int selectedIndex = buildSelector.getSelectedIndex();
    if (selectedIndex != 0) {
      suiteSelector.setEnabled(true);

    }
  }

  private void boardSelected() {
    suiteSelector.setEnabled(false);
    actionButton.setEnabled(false);
    int selectedIndex = boardSelector.getSelectedIndex();
    // Ignore if user select the instruction label.
    if (selectedIndex != 0) {
      loadBuilds(boardSelector.getItemText(boardSelector.getSelectedIndex()));
    }
  }

  /**
   * Call an RPC to get the boards that are connected to the moblab and populate them in the
   * dropdown.
   */
  private void loadBoards() {
    boardSelector.setEnabled(false);
    boardSelector.clear();
    boardSelector.addItem("Select the board");
    MoblabRpcHelper.fetchConnectedBoards(new MoblabRpcCallbacks.FetchConnectedBoardsCallback() {
      @Override
      public void onFetchConnectedBoardsSubmitted(List<String> connectedBoards) {
        for (String connectedBoard : connectedBoards) {
          boardSelector.addItem(connectedBoard);
        }
        boardSelector.setEnabled(true);
      }
    });
  }

  /**
   * Call an RPC to get the pools that are configured on the devices connected to the moblab. 
   * and fill in the .
   */
  private void loadPools() {
    poolSelector.setEnabled(false);
    poolSelector.clear();
    poolSelector.addItem("Select a pool");
    MoblabRpcHelper.fetchConnectedPools(new MoblabRpcCallbacks.FetchConnectedPoolsCallback() {
      @Override
      public void onFetchConnectedPoolsSubmitted(List<String> connectedPools) {
        for (String connectedPool : connectedPools) {
          poolSelector.addItem(connectedPool);
        }
        poolSelector.setEnabled(true);
      }
    });
  }


  /**
   * Make a RPC to get the most recent builds available for the specified board and populate them
   * in the dropdown.
   * @param selectedBoard
   */
  private void loadBuilds(String selectedBoard) {
    buildSelector.setEnabled(false);
    buildSelector.clear();
    buildSelector.addItem("Select the build");
    MoblabRpcHelper.fetchBuildsForBoard(selectedBoard,
        new MoblabRpcCallbacks.FetchBuildsForBoardCallback() {
      @Override
      public void onFetchBuildsForBoardCallbackSubmitted(List<String> boards) {
        for (String board : boards) {
          buildSelector.addItem(board);
        }
        buildSelector.setEnabled(true);
      }
    });
  }

  /**
   * For the selection option of board, build, suite and pool make a RPC call that will instruct
   * AFE to run the suite selected.
   * @param board, a string that specified a device connected to the moblab.
   * @param build, a string that is a valid build for the specified board available in GCS.
   * @param suite, a string that specifies the name of a suite selected to run.
   * @param pool, an optional name of a pool to run the suite in.
   */
  private void runSuite(String board, String build, String suite, String pool) {
    String realPoolLabel = pool;
    if (pool != null && !pool.isEmpty()) {
      realPoolLabel = pool.trim();
    }
    MoblabRpcHelper.runSuite(board, build, suite, realPoolLabel, new RunSuiteCallback() {
      @Override
      public void onRunSuiteComplete() {
        Window.Location.assign("/afe");
      }
    });
  };

}
