package autotest.common.table;

import autotest.common.ui.DateTimeBox;

import com.google.gwt.event.logical.shared.ValueChangeEvent;
import com.google.gwt.event.logical.shared.ValueChangeHandler;
import com.google.gwt.i18n.client.DateTimeFormat;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.Widget;
import com.google.gwt.user.datepicker.client.CalendarUtil;

import java.util.Date;

public class DatetimeSegmentFilter extends SimpleFilter {
    protected DateTimeBox startDatetimeBox;
    protected DateTimeBox endDatetimeBox;
    protected Panel panel;
    protected Label fromLabel;
    protected Label toLabel;
    private String placeHolderStartDatetime;
    private String placeHolderEndDatetime;

    // only allow queries of at most 2 weeks of data to reduce the load on the
    // database.
    private static final long MAXIMUM_TIME_RANGE_MS = 14 * 1000 * 60 * 60 * 24;
    private static final DateTimeFormat dateTimeFormat =
        DateTimeFormat.getFormat("yyyy-MM-dd");
    private static final DateTimeFormat parseFormat =
        DateTimeFormat.getFormat("yyyy-MM-ddTHH:mm");

    public DatetimeSegmentFilter() {
        startDatetimeBox = new DateTimeBox();
        endDatetimeBox = new DateTimeBox();
        fromLabel = new Label("From");
        toLabel = new Label("to");

        panel = new HorizontalPanel();
        panel.add(fromLabel);
        panel.add(startDatetimeBox);
        panel.add(toLabel);
        panel.add(endDatetimeBox);

        Date placeHolderDate = new Date();
        // We want all entries from today, so advance end date to tomorrow.
        CalendarUtil.addDaysToDate(placeHolderDate, 1);
        placeHolderEndDatetime = format(placeHolderDate);
        setEndTimeToPlaceHolderValue();

        CalendarUtil.addDaysToDate(placeHolderDate, -7);
        placeHolderStartDatetime = format(placeHolderDate);
        setStartTimeToPlaceHolderValue();

        addValueChangeHandler(
            new ValueChangeHandler() {
                public void onValueChange(ValueChangeEvent event) {
                    notifyListeners();
                }
            },
            new ValueChangeHandler<String>() {
                /*
                 * Put a 2-week constraint on the width of the date interval;
                 * whenever the endDate changes, update the start date if
                 * needed, and update its minimum Date to be two weeks earlier
                 * than the new endDate value.
                 */
                public void onValueChange(ValueChangeEvent<String> event) {
                    Date newEndDate = parse(event.getValue());
                    Date currentStartDate = parse(startDatetimeBox.getValue());
                    Date startDateConstraint = minimumStartDate(newEndDate);
                    Date newStartDate = (
                        currentStartDate.compareTo(startDateConstraint) > 0
                        ? currentStartDate
                        : startDateConstraint);
                    startDatetimeBox.setValue(format(newStartDate));
                    startDatetimeBox.setMin(format(startDateConstraint));
                    notifyListeners();
                }
            }
        );
    }

    public static String format(Date date) {
        return dateTimeFormat.format(date) + "T00:00";
    }

    public static Date parse(String date) {
        return parseFormat.parse(date);
    }

    public static Date minimumStartDate(Date endDate) {
        long sinceEpoch = endDate.getTime();
        return new Date(sinceEpoch - MAXIMUM_TIME_RANGE_MS);
    }

    @Override
    public Widget getWidget() {
        return panel;
    }

    public void setStartTimeToPlaceHolderValue() {
        startDatetimeBox.setValue(placeHolderStartDatetime);
    }

    public void setEndTimeToPlaceHolderValue() {
        endDatetimeBox.setValue(placeHolderEndDatetime);
    }

    public void addValueChangeHandler(ValueChangeHandler<String> startTimeHandler,
                                      ValueChangeHandler<String> endTimeHandler) {
        startDatetimeBox.addValueChangeHandler(startTimeHandler);
        endDatetimeBox.addValueChangeHandler(endTimeHandler);
    }
}
